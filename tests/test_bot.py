import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch, AsyncMock

from bot.app import app
from smm_engine.scrapers.base import NewsItem

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
    resp = client.post("/api/force-pipeline")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "message": "Pipeline started"}

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
    """Verify that when no basic auth environment variables are set, access is permitted without credentials."""
    with patch("os.getenv", side_effect=lambda key, default=None: None):
        resp = client.get("/")
        assert resp.status_code == 200


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


def test_security_headers_enforced():
    """Verify that secure HTTP headers are included in dashboard and API responses."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "max-age=" in resp.headers["Strict-Transport-Security"]
    assert "Content-Security-Policy" in resp.headers


def test_webhook_security_token():
    """Verify webhook token validation behavior."""
    # 1. Without secret configured: should allow requests
    with patch("os.getenv", side_effect=lambda key, default=None: None):
        payload = {"update_id": 9999, "message": {"chat": {"id": 123}, "text": "hello"}}
        resp = client.post("/webhook", json=payload)
        assert resp.status_code == 200

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



