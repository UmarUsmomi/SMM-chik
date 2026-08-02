import gzip
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from smm_engine.utils.network import UnsafeUrlError, fetch_public_http


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://[::1]/admin",
        "http://169.254.169.254/latest/meta-data/",
        "file:///etc/passwd",
        "https://user:password@example.com/image.jpg",
        "https://example.com:8443/image.jpg",
    ],
)
async def test_fetch_public_http_rejects_unsafe_urls_without_request(url):
    transport = AsyncMock()

    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(UnsafeUrlError):
            await fetch_public_http(client, url, max_bytes=1024)

    transport.handle_async_request.assert_not_awaited()


@pytest.mark.asyncio
async def test_fetch_public_http_rejects_redirect_to_private_address():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})

    with patch(
        "smm_engine.utils.network._resolve_host",
        new=AsyncMock(return_value={"93.184.216.34"}),
    ):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(UnsafeUrlError):
                await fetch_public_http(client, "https://example.com/start", max_bytes=1024)


@pytest.mark.asyncio
async def test_fetch_public_http_limits_response_size():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 1025)

    with patch(
        "smm_engine.utils.network._resolve_host",
        new=AsyncMock(return_value={"93.184.216.34"}),
    ):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(UnsafeUrlError, match="response is too large"):
                await fetch_public_http(client, "https://example.com/image", max_bytes=1024)


@pytest.mark.asyncio
async def test_fetch_public_http_returns_bounded_public_response():
    observed_request = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed_request["url_host"] = request.url.host
        observed_request["host_header"] = request.headers["host"]
        observed_request["sni_hostname"] = request.extensions.get("sni_hostname")
        return httpx.Response(200, headers={"content-type": "image/png"}, content=b"safe")

    with patch(
        "smm_engine.utils.network._resolve_host",
        new=AsyncMock(return_value={"93.184.216.34"}),
    ):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            response = await fetch_public_http(
                client,
                "https://example.com/image",
                max_bytes=1024,
            )

    assert response.status_code == 200
    assert response.content == b"safe"
    assert response.url == httpx.URL("https://example.com/image")
    assert observed_request == {
        "url_host": "93.184.216.34",
        "host_header": "example.com",
        "sni_hostname": b"example.com",
    }


@pytest.mark.asyncio
async def test_fetch_public_http_returns_decoded_compressed_response_once():
    compressed = gzip.compress(b"decoded content")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "content-encoding": "gzip",
                "content-length": str(len(compressed)),
            },
            content=compressed,
        )

    with patch(
        "smm_engine.utils.network._resolve_host",
        new=AsyncMock(return_value={"93.184.216.34"}),
    ):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            response = await fetch_public_http(
                client,
                "https://example.com/compressed",
                max_bytes=1024,
            )

    assert response.content == b"decoded content"
    assert "content-encoding" not in response.headers
    assert response.headers["content-length"] == str(len(b"decoded content"))
