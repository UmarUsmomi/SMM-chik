import logging

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch, AsyncMock

from bot.app import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    """Sets a temporary sqlite path for tests"""
    db_file = tmp_path / "test_bot.db"
    with patch("smm_engine.storage.database.SQLITE_DB_PATH", str(db_file)):
        # Re-initialize DB in app
        import bot.app
        bot.app.db = bot.app.DatabaseManager()
        yield str(db_file)

def test_health_check():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy", "service": "smm-queue-bot"}


@pytest.mark.parametrize(
    ("configured_value", "expected"),
    [
        (None, False),
        ("false", False),
        ("0", False),
        ("true", True),
        ("YES", True),
        ("on", True),
    ],
)
def test_background_scheduler_requires_explicit_opt_in(monkeypatch, configured_value, expected):
    import bot.app

    if configured_value is None:
        monkeypatch.delenv("SCHEDULER_ENABLED", raising=False)
    else:
        monkeypatch.setenv("SCHEDULER_ENABLED", configured_value)

    assert bot.app.is_scheduler_enabled() is expected


def test_production_webhook_registration_requires_secret(monkeypatch):
    import bot.app

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)

    assert bot.app.build_telegram_webhook_payload("https://service.example") is None


def test_webhook_registration_includes_configured_secret(monkeypatch):
    import bot.app

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "delivery-secret")

    assert bot.app.build_telegram_webhook_payload("https://service.example/") == {
        "url": "https://service.example/webhook",
        "secret_token": "delivery-secret",
    }


def test_readiness_check_verifies_database():
    resp = client.get("/readyz")

    assert resp.status_code == 200
    assert resp.json() == {
        "status": "ready",
        "service": "smm-queue-bot",
        "database": "ok",
    }


def test_readiness_check_hides_database_errors():
    marker = "private-readiness-error-marker"

    with patch("bot.app.db.ping", side_effect=RuntimeError(marker)):
        resp = client.get("/readyz")

    assert resp.status_code == 503
    assert resp.json() == {
        "status": "unavailable",
        "service": "smm-queue-bot",
        "database": "error",
    }
    assert marker not in resp.text


def test_production_readiness_fails_closed_when_configuration_is_incomplete():
    with patch(
        "os.getenv",
        side_effect=lambda key, default=None: "production" if key == "ENVIRONMENT" else None,
    ), patch("bot.app.db.ping", return_value=True):
        resp = client.get("/readyz")

    assert resp.status_code == 503
    assert resp.json() == {
        "status": "unavailable",
        "service": "smm-queue-bot",
        "database": "ok",
        "configuration": "error",
    }


def test_production_readiness_accepts_complete_configuration():
    required_values = {
        "ENVIRONMENT": "production",
        "DATABASE_URL": "configured",
        "GEMINI_API_KEY": "configured",
        "TELEGRAM_BOT_TOKEN": "configured",
        "TELEGRAM_CHANNEL_ID": "configured",
        "TELEGRAM_WEBHOOK_SECRET": "configured",
        "TELEGRAM_ADMIN_CHAT_ID": "123456",
        "DASHBOARD_USERNAME": "admin",
        "DASHBOARD_PASSWORD": "configured",
    }

    with patch(
        "os.getenv",
        side_effect=lambda key, default=None: required_values.get(key, default),
    ), patch("bot.app.db.ping", return_value=True):
        resp = client.get("/readyz")

    assert resp.status_code == 200
    assert resp.json() == {
        "status": "ready",
        "service": "smm-queue-bot",
        "database": "ok",
        "configuration": "ok",
    }


def test_http_request_closes_database_connection(tmp_path):
    import sqlite3

    import bot.app

    opened_connections = []
    real_connect = sqlite3.connect

    class TrackingConnection(sqlite3.Connection):
        closed = False

        def close(self):
            self.closed = True
            super().close()

    def capture_connection(*args, **kwargs):
        connection = real_connect(*args, factory=TrackingConnection, **kwargs)
        opened_connections.append(connection)
        return connection

    database_path = tmp_path / "request-scope.db"
    bot.app.db.close_current()
    with patch("smm_engine.storage.database.SQLITE_DB_PATH", str(database_path)), patch(
        "smm_engine.storage.database.sqlite3.connect",
        side_effect=capture_connection,
    ):
        resp = client.get("/readyz")

    assert resp.status_code == 200
    assert opened_connections
    assert all(connection.closed for connection in opened_connections)


@pytest.mark.asyncio
async def test_pipeline_task_closes_database_connection():
    import bot.app

    bot.app.pipeline_running = False
    with patch("bot.app.SMMPipeline") as pipeline_cls, patch.object(
        bot.app.db, "close_current"
    ) as close_current:
        pipeline_cls.return_value.run = AsyncMock(return_value={"processed": 0})
        await bot.app.run_pipeline_task()

    close_current.assert_called_once_with()
    assert bot.app.pipeline_running is False


@pytest.mark.asyncio
async def test_publish_background_task_closes_database_connection():
    import bot.app

    with patch.object(bot.app.db, "get_by_id", return_value=None), patch.object(
        bot.app.db, "close_current"
    ) as close_current:
        await bot.app.publish_item_background(424242, 0, 0)

    close_current.assert_called_once_with()
    assert 424242 not in bot.app.active_publishing_ids


@pytest.mark.asyncio
async def test_publish_background_hides_internal_error_from_operator():
    import bot.app

    marker = "private-publish-error-marker"
    item = {
        "id": 42,
        "source": "source",
        "source_id": "source-id",
        "title": "Original title",
        "url": "https://example.com/article",
        "raw_data": {},
        "status": "pending_review",
        "adapted_title": "Adapted title",
        "adapted_text": "Adapted text",
    }

    with patch.object(bot.app.db, "get_by_id", return_value=item), patch.object(
        bot.app.publisher,
        "publish_post_with_cover",
        new=AsyncMock(side_effect=RuntimeError(marker)),
    ), patch("bot.app.send_bot_message", new_callable=AsyncMock) as send_message:
        await bot.app.publish_item_background(42, 123, 456)

    assert send_message.await_count == 1
    assert marker not in send_message.await_args.args[1]
    assert "внутренняя ошибка" in send_message.await_args.args[1].lower()


@pytest.mark.asyncio
async def test_bot_delivery_error_does_not_log_secret_bearing_exception(caplog):
    import bot.app

    marker = "private-telegram-url-marker"
    mocked_client = AsyncMock()
    mocked_client.post.side_effect = RuntimeError(marker)
    mocked_context = MagicMock()
    mocked_context.__aenter__ = AsyncMock(return_value=mocked_client)
    mocked_context.__aexit__ = AsyncMock(return_value=False)
    caplog.set_level(logging.ERROR, logger="telegram_bot")

    with patch("httpx.AsyncClient", return_value=mocked_context):
        await bot.app.send_bot_message(123, "hello")

    assert marker not in caplog.text


@pytest.mark.asyncio
async def test_successful_telegram_publish_is_recorded_before_optional_threads_failure():
    import bot.app

    item = {
        "id": 43,
        "source": "source",
        "source_id": "source-id-43",
        "title": "Original title",
        "url": "https://example.com/article",
        "raw_data": {},
        "status": "pending_review",
        "adapted_title": "Adapted title",
        "adapted_text": "Adapted text",
    }
    threads_instance = MagicMock()
    threads_instance.publish_post = AsyncMock(side_effect=RuntimeError("threads unavailable"))

    with patch.object(bot.app.db, "get_by_id", return_value=item), patch.object(
        bot.app.publisher,
        "publish_post_with_cover",
        new=AsyncMock(return_value=True),
    ), patch.object(bot.app.db, "mark_published") as mark_published, patch(
        "smm_engine.publishers.threads_pub.ThreadsPublisher",
        return_value=threads_instance,
    ), patch("bot.app.send_bot_message", new_callable=AsyncMock):
        await bot.app.publish_item_background(43, 0, 0)

    mark_published.assert_called_once_with(43)


def test_dashboard_view():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "НейроСофт Гейминг" in resp.text

def test_api_toggle_pause():
    resp = client.post("/api/toggle-pause", json={"active": True})
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "is_paused": False}
    
    resp = client.post("/api/toggle-pause", json={"active": False})
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "is_paused": True}

@patch("bot.app.publisher.publish_post_with_cover", new_callable=AsyncMock)
def test_api_moderate_approve(mock_pub):
    mock_pub.return_value = True
    import bot.app
    item_id = bot.app.db.save_news_item("test", "999", "Api Test Title", "https://api-test.com", {})
    bot.app.db.save_adapted_content(item_id, "Adapted Title", "Adapted Text", status='pending_review')
    
    resp = client.post(f"/api/moderate/{item_id}", json={"action": "approve"})
    assert resp.status_code == 200
    assert resp.json()["action"] == "publishing_started"
    mock_pub.assert_called_once_with("Adapted Title", "Adapted Text", news_item_url="https://api-test.com", raw_data="{}")
    
    # Verify in DB
    item = bot.app.db.get_by_id(item_id)
    assert item["status"] == "published"

def test_api_moderate_reject():
    import bot.app
    item_id = bot.app.db.save_news_item("test", "888", "Api Reject Title", "https://api-reject.com", {})
    bot.app.db.save_adapted_content(item_id, "Adapted Title", "Adapted Text", status='pending_review')
    
    resp = client.post(f"/api/moderate/{item_id}", json={"action": "reject"})
    assert resp.status_code == 200
    assert resp.json()["action"] == "rejected"
    
    # Verify in DB
    item = bot.app.db.get_by_id(item_id)
    assert item["status"] == "rejected"

def test_api_force_pipeline():
    resp = client.post("/api/force-pipeline", json={"confirmed": True})
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "message": "Pipeline started"}


def test_api_force_pipeline_requires_json_confirmation():
    resp = client.post("/api/force-pipeline")
    assert resp.status_code == 422


def test_api_test_telegram_rejects_safe_get_method():
    resp = client.get("/api/test-telegram")
    assert resp.status_code == 405


def test_api_test_models_hides_provider_error_details():
    marker = "private-model-provider-error-marker"

    with patch("smm_engine.config.GEMINI_API_KEY", "configured"), patch(
        "google.generativeai.configure"
    ), patch("google.generativeai.list_models", side_effect=RuntimeError(marker)):
        resp = client.get("/api/test-models")

    assert resp.status_code == 502
    assert resp.json() == {"error": "Model connectivity check failed"}
    assert marker not in resp.text


def test_api_test_telegram_hides_provider_error_details():
    marker = "private-telegram-provider-error-marker"
    mocked_client = AsyncMock()
    mocked_client.post.side_effect = RuntimeError(marker)
    mocked_context = MagicMock()
    mocked_context.__aenter__ = AsyncMock(return_value=mocked_client)
    mocked_context.__aexit__ = AsyncMock(return_value=False)

    with patch("smm_engine.config.TELEGRAM_BOT_TOKEN", "configured"), patch(
        "smm_engine.config.TELEGRAM_CHANNEL_ID", "configured"
    ), patch("httpx.AsyncClient", return_value=mocked_context):
        resp = client.post("/api/test-telegram")

    assert resp.status_code == 502
    assert resp.json() == {"error": "Telegram connectivity check failed"}
    assert marker not in resp.text


@patch("bot.app.send_bot_message", new_callable=AsyncMock)
def test_bot_start(mock_send):
    payload = {
        "update_id": 1000,
        "message": {
            "message_id": 1,
            "chat": {"id": 12345, "type": "private"},
            "text": "/start"
        }
    }
    resp = client.post("/webhook", json=payload)
    assert resp.status_code == 200
    mock_send.assert_called_once()
    assert "Привет!" in mock_send.call_args[0][1]

@patch("bot.app.send_bot_message", new_callable=AsyncMock)
def test_bot_status(mock_send):
    payload = {
        "update_id": 1001,
        "message": {
            "message_id": 2,
            "chat": {"id": 12345, "type": "private"},
            "text": "/status"
        }
    }
    resp = client.post("/webhook", json=payload)
    assert resp.status_code == 200
    mock_send.assert_called_once()
    assert "📊 Текущий статус системы:" in mock_send.call_args[0][1]

@patch("bot.app.send_bot_message", new_callable=AsyncMock)
def test_bot_queue_empty(mock_send):
    payload = {
        "update_id": 1002,
        "message": {
            "message_id": 3,
            "chat": {"id": 12345, "type": "private"},
            "text": "/queue"
        }
    }
    resp = client.post("/webhook", json=payload)
    assert resp.status_code == 200
    mock_send.assert_called_once()
    assert "Очередь пуста!" in mock_send.call_args[0][1]

@patch("bot.app.send_bot_message", new_callable=AsyncMock)
@patch("bot.app.edit_message_text", new_callable=AsyncMock)
@patch("bot.app.answer_callback_query", new_callable=AsyncMock)
@patch("bot.app.publisher.publish_post_with_cover", new_callable=AsyncMock)
def test_bot_approve(mock_pub, mock_answer, mock_edit, mock_send):
    # Save a mock news item to database first
    import bot.app
    item_id = bot.app.db.save_news_item("test", "123", "Test Title", "https://test.com", {})
    bot.app.db.save_adapted_content(item_id, "Adapted Title", "Adapted Text", status='pending_review')
    
    mock_pub.return_value = True
    
    payload = {
        "update_id": 1003,
        "callback_query": {
            "id": "cb_1",
            "message": {
                "message_id": 100,
                "chat": {"id": 12345, "type": "private"},
                "text": "Some text"
            },
            "data": f"approve_{item_id}"
        }
    }
    
    resp = client.post("/webhook", json=payload)
    assert resp.status_code == 200
    mock_pub.assert_called_once_with("Adapted Title", "Adapted Text", news_item_url="https://test.com", raw_data="{}")
    mock_edit.assert_called_once()
    assert "Опубликовано" in mock_edit.call_args[0][2]
    
    # Verify published in DB
    item = bot.app.db.get_by_id(item_id)
    assert item["status"] == "published"


def test_dashboard_security_bypass():
    """Local development remains usable without configuring dashboard credentials."""
    with patch(
        "os.getenv",
        side_effect=lambda key, default=None: "development" if key == "ENVIRONMENT" else None,
    ):
        resp = client.get("/")
        assert resp.status_code == 200


def test_dashboard_fails_closed_in_production_without_credentials():
    """A production configuration error must never expose the admin dashboard."""
    with patch(
        "os.getenv",
        side_effect=lambda key, default=None: "production" if key == "ENVIRONMENT" else None,
    ):
        resp = client.get("/")

    assert resp.status_code == 503
    assert resp.json() == {"detail": "Dashboard authentication is not configured"}


def test_dashboard_security_enforced():
    """Verify that when basic auth environment variables are configured, credentials are required."""
    def mock_getenv(key, default=None):
        if key == "DASHBOARD_USERNAME":
            return "admin"
        if key == "DASHBOARD_PASSWORD":
            return "secret_pass"
        return None

    with patch("os.getenv", side_effect=mock_getenv):
        # 1. Access without credentials should return 401
        resp = client.get("/")
        assert resp.status_code == 401
        assert "WWW-Authenticate" in resp.headers

        # 2. Access with wrong credentials should return 401
        resp = client.get("/", auth=("admin", "wrong"))
        assert resp.status_code == 401

        # 3. Access with correct credentials should return 200
        resp = client.get("/", auth=("admin", "secret_pass"))
        assert resp.status_code == 200


def test_dashboard_rate_limits_repeated_invalid_credentials():
    import bot.app

    def mock_getenv(key, default=None):
        values = {
            "DASHBOARD_USERNAME": "secure_admin",
            "DASHBOARD_PASSWORD": "secure_password",
        }
        return values.get(key, default)

    if hasattr(bot.app, "failed_auth_attempts"):
        bot.app.failed_auth_attempts.clear()

    try:
        with patch("os.getenv", side_effect=mock_getenv):
            for _ in range(5):
                resp = client.get("/", auth=("wrong", "wrong"))
                assert resp.status_code == 401

            blocked = client.get("/", auth=("wrong", "wrong"))

        assert blocked.status_code == 429
        assert blocked.headers["Retry-After"] == "300"
    finally:
        if hasattr(bot.app, "failed_auth_attempts"):
            bot.app.failed_auth_attempts.clear()


def test_security_headers_enforced():
    """Verify that secure HTTP headers are included in dashboard and API responses."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "max-age=" in resp.headers["Strict-Transport-Security"]
    assert resp.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"
    assert resp.headers["Cache-Control"] == "no-store"
    csp = resp.headers["Content-Security-Policy"]
    assert "object-src 'none'" in csp
    assert "base-uri 'self'" in csp
    assert "form-action 'self'" in csp
    assert "frame-ancestors 'none'" in csp


def test_dashboard_dependency_error_hides_internal_details():
    """The operator-facing error page must not expose stack traces or DB details."""
    marker = "private-database-error-marker"

    with patch("bot.app.db.get_stats", side_effect=RuntimeError(marker)):
        resp = client.get("/")

    assert resp.status_code == 503
    assert marker not in resp.text
    assert "Traceback" not in resp.text
    assert "База данных временно недоступна" in resp.text


def test_dashboard_log_renderer_treats_logs_as_text():
    """External error text shown in the dashboard must not become executable HTML."""
    resp = client.get("/")

    assert resp.status_code == 200
    assert "logLine.textContent = log" in resp.text
    assert "container.innerHTML = data.logs.map" not in resp.text


def test_dashboard_pins_chart_dependency_with_integrity_metadata():
    resp = client.get("/")

    assert resp.status_code == 200
    assert "chart.js@4.5.1/dist/chart.umd.min.js" in resp.text
    assert 'integrity="sha384-' in resp.text
    assert 'crossorigin="anonymous"' in resp.text


def test_dashboard_does_not_claim_background_publish_already_succeeded():
    resp = client.get("/")

    assert resp.status_code == 200
    assert "result.action === 'publishing_started'" in resp.text
    assert 'showToast("Публикация запущена. Результат появится в журнале.", "info")' in resp.text


def test_dashboard_does_not_render_unsafe_source_links():
    import bot.app

    item_id = bot.app.db.save_news_item(
        "untrusted",
        "unsafe-url",
        "Unsafe link",
        "javascript:alert('xss')",
        {},
    )
    bot.app.db.update_scoring(item_id, 10, "Rejected", status="rejected")

    resp = client.get("/")

    assert resp.status_code == 200
    assert "javascript:alert" not in resp.text


def test_dashboard_renders_safe_source_links_with_opener_protection():
    import bot.app

    item_id = bot.app.db.save_news_item(
        "trusted",
        "safe-url",
        "Safe link",
        "https://example.com/news",
        {},
    )
    bot.app.db.update_scoring(item_id, 10, "Rejected", status="rejected")

    resp = client.get("/")

    assert resp.status_code == 200
    assert 'href="https://example.com/news"' in resp.text
    assert 'rel="noopener noreferrer"' in resp.text


def test_webhook_security_token():
    """Verify webhook token validation behavior."""
    # 1. Without secret configured: should allow requests
    with patch("os.getenv", side_effect=lambda key, default=None: None):
        payload = {"update_id": 9999, "message": {"chat": {"id": 123}, "text": "hello"}}
        resp = client.post("/webhook", json=payload)
        assert resp.status_code == 200


def test_webhook_fails_closed_in_production_without_secret():
    """Production must not accept Telegram updates without webhook authentication."""
    with patch(
        "os.getenv",
        side_effect=lambda key, default=None: "production" if key == "ENVIRONMENT" else None,
    ):
        resp = client.post(
            "/webhook",
            json={"update_id": 9998, "message": {"chat": {"id": 123}, "text": "/pause"}},
        )

    assert resp.status_code == 503
    assert resp.json() == {"detail": "Webhook authentication is not configured"}


def test_webhook_rejects_non_object_payload():
    resp = client.post("/webhook", json=["not", "an", "update"])

    assert resp.status_code == 400
    assert resp.json() == {"detail": "Invalid Telegram update"}


def test_webhook_rejects_declared_oversized_payload():
    resp = client.post(
        "/webhook",
        headers={"Content-Length": str(1024 * 1024 + 1)},
        content=b"{}",
    )

    assert resp.status_code == 413
    assert resp.json() == {"detail": "Telegram update is too large"}


def test_webhook_rejects_oversized_body_even_with_false_length_header():
    resp = client.post(
        "/webhook",
        headers={"Content-Length": "2", "Content-Type": "application/json"},
        content=b'{' + b'"padding":"' + (b"x" * (1024 * 1024)) + b'"}',
    )

    assert resp.status_code == 413
    assert resp.json() == {"detail": "Telegram update is too large"}


@patch("bot.app.send_bot_message", new_callable=AsyncMock)
def test_webhook_ignores_commands_from_non_admin_chat(mock_send):
    """A valid Telegram delivery secret does not grant operator authorization."""
    def mock_getenv(key, default=None):
        values = {
            "ENVIRONMENT": "production",
            "TELEGRAM_WEBHOOK_SECRET": "delivery-secret",
            "TELEGRAM_ADMIN_CHAT_ID": "998877",
        }
        return values.get(key, default)

    with patch("os.getenv", side_effect=mock_getenv):
        resp = client.post(
            "/webhook",
            headers={"X-Telegram-Bot-Api-Secret-Token": "delivery-secret"},
            json={"update_id": 1006, "message": {"chat": {"id": 111222}, "text": "/pause"}},
        )

    assert resp.status_code == 200
    assert resp.json() == {"status": "ignored"}
    assert mock_send.await_count == 0

    import bot.app
    assert bot.app.db.get_setting("is_paused") is None
    assert bot.app.db.get_setting("admin_chat_id") is None


@patch("bot.app.send_bot_message", new_callable=AsyncMock)
def test_webhook_production_does_not_trust_legacy_stored_admin(mock_send):
    """Legacy auto-enrollment state must not authorize a production operator."""
    import bot.app

    def mock_getenv(key, default=None):
        values = {
            "ENVIRONMENT": "production",
            "TELEGRAM_WEBHOOK_SECRET": "delivery-secret",
        }
        return values.get(key, default)

    with patch("os.getenv", side_effect=mock_getenv), patch.object(
        bot.app.db, "get_setting", return_value="998877"
    ):
        resp = client.post(
            "/webhook",
            headers={"X-Telegram-Bot-Api-Secret-Token": "delivery-secret"},
            json={"update_id": 1008, "message": {"chat": {"id": 998877}, "text": "/pause"}},
        )

    assert resp.status_code == 200
    assert resp.json() == {"status": "ignored"}
    assert mock_send.await_count == 0


@patch("bot.app.send_bot_message", new_callable=AsyncMock)
def test_webhook_does_not_log_message_contents(mock_send, caplog):
    """Webhook logs contain routing metadata, not user message contents."""
    marker = "private-message-content-marker"
    caplog.set_level(logging.INFO, logger="telegram_bot")

    with patch("os.getenv", side_effect=lambda key, default=None: default):
        resp = client.post(
            "/webhook",
            json={"update_id": 1007, "message": {"chat": {"id": 12345}, "text": marker}},
        )

    assert resp.status_code == 200
    assert marker not in caplog.text

    # 2. With secret configured
    def mock_getenv(key, default=None):
        if key == "TELEGRAM_WEBHOOK_SECRET":
            return "super_secret_webhook_token"
        return None

    with patch("os.getenv", side_effect=mock_getenv):
        payload = {"update_id": 9999, "message": {"chat": {"id": 123}, "text": "hello"}}
        
        # Access with incorrect/missing token -> 403 Forbidden
        resp = client.post("/webhook", json=payload)
        assert resp.status_code == 403

        resp = client.post(
            "/webhook", 
            json=payload, 
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong_token"}
        )
        assert resp.status_code == 403

        # Access with correct token -> 200 OK
        resp = client.post(
            "/webhook", 
            json=payload, 
            headers={"X-Telegram-Bot-Api-Secret-Token": "super_secret_webhook_token"}
        )
        assert resp.status_code == 200


def test_api_moderate_trash():
    import bot.app
    item_id = bot.app.db.save_news_item("test", "777", "Api Trash Title", "https://api-trash.com", {})
    bot.app.db.save_adapted_content(item_id, "Adapted Title", "Adapted Text", status='pending_review')
    
    resp = client.post(f"/api/moderate/{item_id}", json={"action": "trash"})
    assert resp.status_code == 200
    assert resp.json()["action"] == "trash"
    
    # Verify in DB
    item = bot.app.db.get_by_id(item_id)
    assert item["status"] == "trash"


def test_webhook_trash_callback():
    import bot.app
    item_id = bot.app.db.save_news_item("test", "666", "Webhook Trash Title", "https://web-trash.com", {})
    bot.app.db.save_adapted_content(item_id, "Adapted Title", "Adapted Text", status='pending_review')
    
    payload = {
        "update_id": 1004,
        "callback_query": {
            "id": "cb_2",
            "message": {
                "message_id": 101,
                "chat": {"id": 12345, "type": "private"},
                "text": "Some text"
            },
            "data": f"trash_{item_id}"
        }
    }
    
    with patch("bot.app.answer_callback_query", new_callable=AsyncMock) as mock_answer, \
         patch("bot.app.edit_message_text", new_callable=AsyncMock) as mock_edit:
         
        resp = client.post("/webhook", json=payload)
        assert resp.status_code == 200
        mock_answer.assert_called_once()
        mock_edit.assert_called_once()
        assert "В мусоре" in mock_edit.call_args[0][2]
        
    item = bot.app.db.get_by_id(item_id)
    assert item["status"] == "trash"


def test_auto_register_admin_chat_id():
    import bot.app
    # Reset admin_chat_id in settings first
    bot.app.db.set_setting("admin_chat_id", "")
    
    payload = {
        "update_id": 1005,
        "message": {
            "message_id": 5,
            "chat": {"id": 998877, "type": "private"},
            "text": "/start"
        }
    }
    
    with patch("bot.app.send_bot_message", new_callable=AsyncMock):
        resp = client.post("/webhook", json=payload)
        assert resp.status_code == 200
        
    admin_chat = bot.app.db.get_setting("admin_chat_id")
    assert admin_chat == "998877"
