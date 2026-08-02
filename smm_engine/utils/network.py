"""Bounded HTTP fetching for URLs supplied by external content sources."""

import asyncio
import ipaddress
import socket
from urllib.parse import SplitResult, urljoin, urlsplit, urlunsplit

import httpx


class UnsafeUrlError(ValueError):
    """Raised when a URL could reach a non-public host or exceed safe limits."""


async def _resolve_host(host: str, port: int) -> set[str]:
    loop = asyncio.get_running_loop()
    try:
        results = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise UnsafeUrlError("URL host could not be resolved") from exc
    return {result[4][0] for result in results}


async def _validate_public_http_url(url: str) -> tuple[SplitResult, tuple[str, ...]]:
    if not isinstance(url, str):
        raise UnsafeUrlError("URL must be a string")

    try:
        parsed = urlsplit(url)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise UnsafeUrlError("URL is malformed") from exc

    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UnsafeUrlError("Only HTTP(S) URLs are allowed")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeUrlError("URL credentials are not allowed")
    if port not in {80, 443}:
        raise UnsafeUrlError("URL port is not allowed")

    try:
        addresses = {str(ipaddress.ip_address(parsed.hostname))}
    except ValueError:
        addresses = await _resolve_host(parsed.hostname, port)

    if not addresses:
        raise UnsafeUrlError("URL host has no address")

    validated_addresses = []
    for address in addresses:
        try:
            parsed_address = ipaddress.ip_address(address)
            if not parsed_address.is_global:
                raise UnsafeUrlError("URL resolves to a non-public address")
            validated_addresses.append(parsed_address)
        except ValueError as exc:
            raise UnsafeUrlError("URL host returned an invalid address") from exc

    validated_addresses.sort(key=lambda address: (address.version, int(address)))
    return parsed, tuple(str(address) for address in validated_addresses)


def _pinned_request_target(
    parsed: SplitResult,
    address: str,
) -> tuple[str, str, bytes]:
    """Build an IP-pinned URL while preserving HTTP Host and TLS identity."""
    address_value = ipaddress.ip_address(address)
    network_host = f"[{address}]" if address_value.version == 6 else address
    if parsed.port is not None:
        network_host = f"{network_host}:{parsed.port}"

    logical_host = parsed.hostname or ""
    sni_hostname = logical_host.encode("idna")
    ascii_logical_host = sni_hostname.decode("ascii")
    host_header = (
        f"[{ascii_logical_host}]" if ":" in ascii_logical_host else ascii_logical_host
    )
    if parsed.port is not None:
        host_header = f"{host_header}:{parsed.port}"

    pinned_url = urlunsplit(
        (parsed.scheme, network_host, parsed.path, parsed.query, "")
    )
    return pinned_url, host_header, sni_hostname


async def fetch_public_http(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_bytes: int,
    max_redirects: int = 3,
    **request_kwargs,
) -> httpx.Response:
    """Fetch a bounded public HTTP(S) response and validate every redirect target."""
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")

    base_headers = httpx.Headers(request_kwargs.pop("headers", None))
    base_extensions = dict(request_kwargs.pop("extensions", {}))
    current_url = url
    for redirect_count in range(max_redirects + 1):
        parsed, addresses = await _validate_public_http_url(current_url)
        pinned_url, host_header, sni_hostname = _pinned_request_target(
            parsed,
            addresses[0],
        )
        request_headers = base_headers.copy()
        request_headers["host"] = host_header
        request_extensions = {**base_extensions, "sni_hostname": sni_hostname}

        async with client.stream(
            "GET",
            pinned_url,
            follow_redirects=False,
            headers=request_headers,
            extensions=request_extensions,
            **request_kwargs,
        ) as response:
            if response.is_redirect:
                location = response.headers.get("location")
                if not location or redirect_count >= max_redirects:
                    raise UnsafeUrlError("Too many or invalid redirects")
                current_url = urljoin(current_url, location)
                continue

            content_length = response.headers.get("content-length")
            if content_length:
                try:
                    declared_length = int(content_length)
                except ValueError:
                    declared_length = 0
                if declared_length > max_bytes:
                    raise UnsafeUrlError("HTTP response is too large")

            content = bytearray()
            async for chunk in response.aiter_bytes():
                content.extend(chunk)
                if len(content) > max_bytes:
                    raise UnsafeUrlError("HTTP response is too large")

            decoded_headers = response.headers.copy()
            decoded_headers.pop("content-encoding", None)
            decoded_headers.pop("transfer-encoding", None)
            decoded_headers["content-length"] = str(len(content))

            return httpx.Response(
                status_code=response.status_code,
                headers=decoded_headers,
                content=bytes(content),
                request=httpx.Request("GET", current_url),
            )

    raise UnsafeUrlError("Too many redirects")
