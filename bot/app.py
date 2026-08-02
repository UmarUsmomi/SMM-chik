import logging
import asyncio
import ipaddress
import json
import os
import secrets
import time
from urllib.parse import urlsplit
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
import httpx
from typing import Literal, Optional

from smm_engine.config import TELEGRAM_BOT_TOKEN
from smm_engine.storage.database import DatabaseManager
from smm_engine.publishers.telegram_pub import TelegramPublisher
from smm_engine.pipeline import SMMPipeline

import collections

class MemoryLogHandler(logging.Handler):
    def __init__(self, capacity=100):
        super().__init__()
        self.capacity = capacity
        self.logs = collections.deque(maxlen=capacity)

    def emit(self, record):
        try:
            msg = self.format(record)
            self.logs.append(msg)
        except Exception:
            self.handleError(record)

    def get_logs(self):
        return list(self.logs)

# Create and configure memory log handler
memory_log_handler = MemoryLogHandler()
memory_log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))

# Configure logging
logging.basicConfig(level=logging.INFO)
logging.getLogger().addHandler(memory_log_handler)

logger = logging.getLogger("telegram_bot")


def is_scheduler_enabled() -> bool:
    """Keep the web-process scheduler opt-in to avoid duplicate cron runs."""
    return (os.getenv("SCHEDULER_ENABLED") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def build_telegram_webhook_payload(render_url: str) -> Optional[dict]:
    """Build a webhook registration payload, failing closed in production."""
    webhook_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    if not webhook_secret and is_production_environment():
        return None

    payload = {"url": f"{render_url.rstrip('/')}/webhook"}
    if webhook_secret:
        payload["secret_token"] = webhook_secret
    return payload


async def scheduler_loop():
    """Background task to run pipeline automatically at regular intervals."""
    import os
    from datetime import datetime, timezone
    
    interval_hours = float(os.getenv("PARSING_INTERVAL_HOURS", "3.0"))
    interval_seconds = int(interval_hours * 3600)
    
    logger.info(f"Background scheduler started. Interval: {interval_hours} hours ({interval_seconds} seconds).")
    
    # Wait for the application to be fully up (e.g., 30 seconds)
    await asyncio.sleep(30)
    
    while True:
        try:
            last_run_str = db.get_setting("last_pipeline_run")
            if last_run_str:
                try:
                    last_run = datetime.fromisoformat(last_run_str)
                    if last_run.tzinfo is None:
                        last_run = last_run.replace(tzinfo=timezone.utc)
                    elapsed = (datetime.now(timezone.utc) - last_run).total_seconds()
                    if elapsed < interval_seconds:
                        remaining = int(interval_seconds - elapsed)
                        logger.info(f"Scheduler: Pipeline ran recently ({elapsed:.1f}s ago). Sleeping remaining {remaining} seconds.")
                        await asyncio.sleep(remaining)
                        continue
                except Exception as ex:
                    logger.error(f"Scheduler: Error parsing last run timestamp: {ex}")
            
            logger.info("Scheduler: Triggering auto-pipeline run...")
            db.set_setting("last_pipeline_run", datetime.now(timezone.utc).isoformat())
            await run_pipeline_task()
        except Exception as exc:
            logger.error("Scheduled pipeline failed (%s)", type(exc).__name__)
            
        logger.info(f"Scheduler: Sleeping for {interval_seconds} seconds...")
        await asyncio.sleep(interval_seconds)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Auto-registers Telegram Webhook and starts background scheduler on startup"""
    import os
    render_url = os.getenv("RENDER_EXTERNAL_URL")
    if render_url and TELEGRAM_BOT_TOKEN:
        payload = build_telegram_webhook_payload(render_url)
        set_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"

        if payload is None:
            logger.error("Skipped Telegram webhook registration: production secret is missing")
        else:
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(set_url, json=payload, timeout=10)
                    response_data = resp.json()
                    if resp.is_success and response_data.get("ok"):
                        logger.info("Telegram webhook registration succeeded")
                    else:
                        logger.error(
                            "Telegram webhook registration failed with status %s",
                            resp.status_code,
                        )
            except Exception as exc:
                logger.error(
                    "Telegram webhook registration failed (%s)",
                    type(exc).__name__,
                )
            
    # GitHub Actions is the production scheduler. Running both schedulers can
    # publish the same item twice because their process-local locks are separate.
    scheduler_task = None
    if is_scheduler_enabled():
        scheduler_task = asyncio.create_task(scheduler_loop())
    else:
        logger.info("In-process scheduler is disabled; expecting an external cron runner")
    
    yield
    
    # Cancel Scheduler Task on shutdown
    if scheduler_task is not None:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass

async def database_request_scope():
    """Close the context-local database connection in the request task itself."""
    try:
        yield
    finally:
        db.close_current()


app = FastAPI(
    title="SMM Automator Queue Bot",
    lifespan=lifespan,
    dependencies=[Depends(database_request_scope)],
)

@app.middleware("http")
async def add_security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path == "/" or request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    
    # Content-Security-Policy (allows local assets, fonts, CDN Chart.js)
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    )
    response.headers["Content-Security-Policy"] = csp
    return response

db = DatabaseManager()
publisher = TelegramPublisher()
templates = Jinja2Templates(directory="web/templates")


def safe_external_url(value: object) -> str:
    """Return a browser-safe public HTTP(S) link or an empty string."""
    if not isinstance(value, str):
        return ""
    try:
        parsed = urlsplit(value)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        return ""

    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or port not in {80, 443}
    ):
        return ""

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        return ""
    try:
        if not ipaddress.ip_address(hostname).is_global:
            return ""
    except ValueError:
        pass
    return value


templates.env.filters["safe_external_url"] = safe_external_url

security = HTTPBasic(auto_error=False)

AUTH_FAILURE_LIMIT = 5
AUTH_FAILURE_WINDOW_SECONDS = 300
AUTH_FAILURE_CLIENT_LIMIT = 1000
failed_auth_attempts: dict[str, collections.deque[float]] = {}

def is_production_environment() -> bool:
    """Return whether the service is running in a production deployment."""
    environment = (os.getenv("ENVIRONMENT") or "").strip().lower()
    return environment in {"production", "prod"} or bool(os.getenv("RENDER_EXTERNAL_URL"))


PRODUCTION_REQUIRED_ENVIRONMENT = (
    "DATABASE_URL",
    "GEMINI_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHANNEL_ID",
    "TELEGRAM_WEBHOOK_SECRET",
    "TELEGRAM_ADMIN_CHAT_ID",
    "DASHBOARD_USERNAME",
    "DASHBOARD_PASSWORD",
)


def production_configuration_ready() -> bool:
    if not is_production_environment():
        return True
    return all(
        bool((os.getenv(name) or "").strip())
        for name in PRODUCTION_REQUIRED_ENVIRONMENT
    )


async def authenticate_dashboard(
    request: Request,
    credentials: Optional[HTTPBasicCredentials] = Depends(security),
):
    username = os.getenv("DASHBOARD_USERNAME")
    password = os.getenv("DASHBOARD_PASSWORD")
    
    # Local development stays convenient, but a deployed service must fail closed.
    if not username or not password:
        if is_production_environment():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Dashboard authentication is not configured",
            )
        return None
        
    client_key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    if (
        client_key not in failed_auth_attempts
        and len(failed_auth_attempts) >= AUTH_FAILURE_CLIENT_LIMIT
    ):
        failed_auth_attempts.pop(next(iter(failed_auth_attempts)))
    recent_failures = failed_auth_attempts.setdefault(client_key, collections.deque())
    cutoff = now - AUTH_FAILURE_WINDOW_SECONDS
    while recent_failures and recent_failures[0] <= cutoff:
        recent_failures.popleft()

    if len(recent_failures) >= AUTH_FAILURE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts",
            headers={"Retry-After": str(AUTH_FAILURE_WINDOW_SECONDS)},
        )

    if not credentials:
        recent_failures.append(now)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )
        
    correct_username = secrets.compare_digest(credentials.username, username)
    correct_password = secrets.compare_digest(credentials.password, password)
    if not (correct_username and correct_password):
        recent_failures.append(now)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    failed_auth_attempts.pop(client_key, None)
    return credentials.username


def is_authorized_telegram_chat(chat_id: int, *, allow_development_bootstrap: bool = False) -> bool:
    """Authorize Telegram operator actions independently from webhook delivery auth."""
    configured_admin = os.getenv("TELEGRAM_ADMIN_CHAT_ID")
    configured_admin = configured_admin.strip() if configured_admin else ""

    # Older versions let any first command overwrite the stored administrator.
    # Production therefore trusts only an explicit environment value.
    if is_production_environment():
        return bool(configured_admin) and secrets.compare_digest(
            str(chat_id),
            configured_admin,
        )

    stored_admin = db.get_setting("admin_chat_id")
    expected_admin = configured_admin or str(stored_admin or "").strip()

    if expected_admin:
        return secrets.compare_digest(str(chat_id), expected_admin)

    if allow_development_bootstrap:
        db.set_setting("admin_chat_id", str(chat_id))
        logger.info("Registered the first local Telegram admin chat")
    return True

# State variables to prevent concurrent pipeline runs
pipeline_running = False
pipeline_lock = asyncio.Lock()

# Deduplication state for publishing to prevent duplicate posting via webhook retries
active_publishing_ids = set()
publishing_lock = asyncio.Lock()

# FSM state for /test_image command
test_image_states = {}  # chat_id -> {"prompt": str, "awaiting": str}

async def publish_item_background(item_id: int, chat_id: int, message_id: int):
    """Background task to publish post, preventing duplicate execution and webhook timeouts."""
    async with publishing_lock:
        if item_id in active_publishing_ids:
            logger.info(f"Item {item_id} is already in the process of publishing. Skipping duplicate run.")
            return
        active_publishing_ids.add(item_id)
        
    try:
        item = db.get_by_id(item_id)
        if not item:
            logger.error(f"Item {item_id} not found in database for background publishing.")
            return
            
        if item["status"] == "published":
            logger.info(f"Item {item_id} status is already 'published'. Skipping background publish.")
            return

        title = item["adapted_title"]
        text = item["adapted_text"]
        
        # If it failed to adapt earlier (None or literal 'None' string), adapt on the fly
        is_adapted_valid = (
            title and text and 
            title.strip().lower() != "none" and 
            text.strip().lower() != "none"
        )
        
        if not is_adapted_valid:
            logger.info(f"Item {item_id} has invalid or missing adapted content. Adapting on the fly...")
            from smm_engine.content.adapter import ContentAdapter
            from smm_engine.scrapers.base import NewsItem
            adapter = ContentAdapter()
            
            db_raw_data = item.get("raw_data")
            parsed_raw = {}
            if db_raw_data:
                if isinstance(db_raw_data, str):
                    try:
                        import json
                        parsed_raw = json.loads(db_raw_data)
                    except Exception:
                        pass
                elif isinstance(db_raw_data, dict):
                    parsed_raw = db_raw_data

            news_item = NewsItem(
                source=item["source"],
                source_id=item["source_id"],
                title=item["title"],
                url=item["url"],
                raw_data=parsed_raw
            )
            try:
                adapted = await adapter.adapt_news(news_item)
                if adapted and adapted.get("title") and adapted.get("text"):
                    title = adapted["title"]
                    text = adapted["text"]
                    if title.strip().lower() == "none" or text.strip().lower() == "none":
                        raise Exception("Adapter returned literal 'None' string")
                    db.save_adapted_content(item_id, title, text, status=item["status"])
                else:
                    raise Exception("Adapter returned empty content")
            except Exception as ex:
                logger.error(f"Failed to adapt item {item_id} on the fly: {ex}")
                title = item["title"]
                text = f"<b>{item['title']}</b>"

        success = await publisher.publish_post_with_cover(
            title, 
            text,
            news_item_url=item.get("url"),
            raw_data=item.get("raw_data")
        )
        if success:
            # Record the primary Telegram side effect before optional channels.
            # Otherwise a Threads outage can leave the item pending and cause a
            # duplicate Telegram post on retry.
            db.mark_published(item_id)

            try:
                from smm_engine.publishers.threads_pub import ThreadsPublisher

                threads_pub = ThreadsPublisher()
                await threads_pub.publish_post(f"{title}\n\n{text}")
            except Exception as exc:
                logger.warning(
                    "Optional Threads publish failed for item %s (%s)",
                    item_id,
                    type(exc).__name__,
                )
            
            # If triggered from Telegram Bot, update the inline moderation message
            if chat_id != 0 and message_id != 0:
                await edit_message_text(
                    chat_id, 
                    message_id, 
                    f"<b>✅ Опубликовано в канал:</b>\n{title}"
                )
        else:
            if chat_id != 0:
                await send_bot_message(chat_id, f"❌ Ошибка при отправке сообщения в канал (ID: {item_id}).")
    except Exception as exc:
        logger.error(
            "Background publish failed for item %s (%s)",
            item_id,
            type(exc).__name__,
        )
        if chat_id != 0:
            await send_bot_message(
                chat_id,
                f"❌ Внутренняя ошибка при публикации (ID: {item_id}). Проверьте журнал панели.",
            )
    finally:
        async with publishing_lock:
            active_publishing_ids.discard(item_id)
        db.close_current()



async def send_bot_message(chat_id: int, text: str, reply_markup: dict = None):
    """Helper to send a message to a user in the bot"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
        
    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload, timeout=10)
    except Exception as exc:
        logger.error("Telegram message delivery failed (%s)", type(exc).__name__)

async def answer_callback_query(callback_query_id: str, text: str):
    """Helper to answer inline callback query"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
    payload = {
        "callback_query_id": callback_query_id,
        "text": text
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload, timeout=10)
    except Exception as exc:
        logger.error("Telegram callback answer failed (%s)", type(exc).__name__)

async def edit_message_text(chat_id: int, message_id: int, text: str):
    """Helper to edit bot's message text and remove buttons"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload, timeout=10)
    except Exception as exc:
        logger.error("Telegram message edit failed (%s)", type(exc).__name__)

async def run_pipeline_task():
    """Manually triggers the SMM pipeline in background with concurrency guard"""
    global pipeline_running
    async with pipeline_lock:
        if pipeline_running:
            logger.info("Pipeline is already running, skipping duplicate run.")
            return
        pipeline_running = True
        
    try:
        logger.info("Manual pipeline run triggered via bot...")
        pipeline = SMMPipeline()
        await pipeline.run()
    except Exception as exc:
        logger.error("Manual pipeline execution failed (%s)", type(exc).__name__)
    finally:
        async with pipeline_lock:
            pipeline_running = False
        db.close_current()

@app.post("/webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    """Main webhook endpoint for Telegram Bot Updates"""
    # 0. Check secret token if configured
    webhook_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    if not webhook_secret:
        if is_production_environment():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Webhook authentication is not configured",
            )
    else:
        token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if not token or not secrets.compare_digest(token, webhook_secret):
            logger.warning("Rejected unauthorized webhook request: invalid secret token")
            raise HTTPException(status_code=403, detail="Forbidden")

    content_length = request.headers.get("Content-Length")
    if content_length:
        try:
            declared_size = int(content_length)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length")
        if declared_size > 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Telegram update is too large",
            )

    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Telegram update is too large",
            )

    try:
        update = json.loads(body)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid Telegram update") from exc
    if not isinstance(update, dict):
        raise HTTPException(status_code=400, detail="Invalid Telegram update")

    try:
        update_type = next((key for key in ("message", "callback_query") if key in update), "other")
        logger.info("Received Telegram update id=%s type=%s", update.get("update_id"), update_type)
        
        # 1. Handle commands/text messages
        if "message" in update:
            message = update["message"]
            chat_id = message["chat"]["id"]
            text = message.get("text", "")
            
            if not is_authorized_telegram_chat(
                chat_id,
                allow_development_bootstrap=text.startswith("/"),
            ):
                logger.warning("Ignored Telegram message from an unauthorized chat")
                return {"status": "ignored"}
            
            if text == "/start":
                welcome = (
                    "<b>Привет! Я бот управления SMM Автоматизатором.</b>\n\n"
                    "Команды:\n"
                    "/status — Статистика и состояние системы\n"
                    "/queue — Очередь постов на модерацию\n"
                    "/pause — Приостановить автопубликацию (все посты в очередь)\n"
                    "/resume — Включить автопубликацию (85+ сразу в канал)\n"
                    "/force — Запустить парсинг и публикацию вручную\n"
                    "/test_image — Тестировать генераторы изображений\n"
                    "/reset — Запросить подтверждение очистки базы данных"
                )
                await send_bot_message(chat_id, welcome)
                
            elif text == "/status":
                # Get stats from database
                stats = db.get_stats()
                
                is_paused = db.get_setting("is_paused", "false") == "true"
                pause_status = "⏸️ ПРИОСТАНОВЛЕНА (все посты в очередь)" if is_paused else "▶️ АКТИВНА (85+ публикуются авто)"
                
                stats_msg = (
                    "<b>📊 Текущий статус системы:</b>\n\n"
                    f"<b>Автопубликация:</b> {pause_status}\n\n"
                    f"▫️ Спарсено (новые): {stats.get('parsed', 0)}\n"
                    f"⏳ На модерации (очередь): {stats.get('pending_review', 0)}\n"
                    f"✅ Опубликовано: {stats.get('published', 0)}\n"
                    f"❌ Отклонено: {stats.get('rejected', 0)}"
                )
                await send_bot_message(chat_id, stats_msg)
                
            elif text == "/pause":
                db.set_setting("is_paused", "true")
                await send_bot_message(chat_id, "<b>⏸️ Автопубликация приостановлена.</b> Теперь все посты с рейтингом 70+ будут направляться в очередь на модерацию.")
                
            elif text == "/resume":
                db.set_setting("is_paused", "false")
                await send_bot_message(chat_id, "<b>▶️ Автопубликация возобновлена.</b> Посты с рейтингом 85+ будут публиковаться автоматически.")
                
            elif text == "/queue":
                # Retrieve pending review items
                pending = db.get_queue(status='pending_review', limit=5)
                if not pending:
                    await send_bot_message(chat_id, "<b>Очередь пуста!</b> Постов на модерации нет. 🏖️")
                    return {"status": "ok"}
                    
                for item in pending:
                    preview_title = publisher._escape_html(item['adapted_title']) if item['adapted_title'] else "<i>Без заголовка</i>"
                    preview_text = publisher._format_markdown_to_html(item['adapted_text']) if item['adapted_text'] else "<i>Текст не адаптирован</i>"
                    msg = (
                        f"<b>🔥 Новость в очереди (ID: {item['id']})</b>\n"
                        f"<b>Источник:</b> {item['source']}\n"
                        f"<b>Оригинальный заголовок:</b> {publisher._escape_html(item['title'])}\n"
                        f"<b>Скоринг:</b> {item['score']}/100\n"
                        f"<b>Почему:</b> {publisher._escape_html(item['score_reason'])}\n\n"
                        f"--- <b>ПРЕВЬЮ ПОСТА</b> ---\n"
                        f"<b>{preview_title}</b>\n\n"
                        f"{preview_text}"
                    )
                    
                    keyboard = {
                        "inline_keyboard": [
                            [
                                {"text": "✅ Опубликовать", "callback_data": f"approve_{item['id']}"},
                                {"text": "❌ Отклонить", "callback_data": f"reject_{item['id']}"}
                            ]
                        ]
                    }
                    await send_bot_message(chat_id, msg, reply_markup=keyboard)
                    
            elif text == "/force":
                await send_bot_message(chat_id, "<b>Запускаю SMM pipeline в фоновом режиме... 🚀</b>")
                background_tasks.add_task(run_pipeline_task)
                
            elif text == "/clear" or text == "/reset":
                await send_bot_message(
                    chat_id,
                    "<b>⚠️ Очистка удалит всю историю новостей.</b> "
                    "Для подтверждения отправьте точную команду <code>/reset CONFIRM</code>.",
                )

            elif text == "/reset CONFIRM":
                db.clear_all_news()
                await send_bot_message(chat_id, "<b>🧹 База данных новостей очищена!</b> Теперь вы можете запустить <code>/force</code> для повторного парсинга и тестирования.")
                
            elif text == "/test_image":
                test_image_states[chat_id] = {"awaiting": "prompt"}
                await send_bot_message(chat_id, "<b>🖼 Тест генерации изображений</b>\n\nНапишите промпт для генерации изображения:")
                
            elif not text.startswith("/") and chat_id in test_image_states:
                state = test_image_states[chat_id]
                if state.get("awaiting") == "prompt":
                    test_image_states[chat_id] = {"prompt": text, "awaiting": "generator"}
                    keyboard = {
                        "inline_keyboard": [
                            [
                                {"text": "🖼 Pollinations", "callback_data": f"gen_pollinations_{chat_id}"},
                            ],
                            [
                                {"text": "☁️ Cloudflare", "callback_data": f"gen_cloudflare_{chat_id}"},
                            ],
                            [
                                {"text": "🤗 HuggingFace", "callback_data": f"gen_huggingface_{chat_id}"},
                            ]
                        ]
                    }
                    await send_bot_message(chat_id, f"<b>Промпт:</b> {publisher._escape_html(text)}\n\nВыберите генератор:", reply_markup=keyboard)
                
        # 2. Handle callback queries from buttons
        elif "callback_query" in update:
            cb = update["callback_query"]
            cb_id = cb["id"]
            chat_id = cb["message"]["chat"]["id"]
            message_id = cb["message"]["message_id"]
            data = cb.get("data", "")

            if not is_authorized_telegram_chat(chat_id):
                logger.warning("Ignored Telegram callback from an unauthorized chat")
                return {"status": "ignored"}
            
            if data.startswith("approve_"):
                item_id = int(data.split("_")[1])
                item = db.get_by_id(item_id)
                
                if not item:
                    await answer_callback_query(cb_id, "Новость не найдена в базе!")
                    return {"status": "ok"}
                    
                if item["status"] == "published":
                    await answer_callback_query(cb_id, "Эта новость уже опубликована!")
                    return {"status": "ok"}
                    
                await answer_callback_query(cb_id, "Публикую...")
                background_tasks.add_task(publish_item_background, item_id, chat_id, message_id)
                    
            elif data.startswith("reject_"):
                item_id = int(data.split("_")[1])
                item = db.get_by_id(item_id)
                
                if not item:
                    await answer_callback_query(cb_id, "Новость не найдена!")
                    return {"status": "ok"}
                    
                await answer_callback_query(cb_id, "Перенесено в корзину.")
                db.update_scoring(item_id, item["score"], item["score_reason"], status='rejected')
                await edit_message_text(
                    chat_id, 
                    message_id, 
                    f"<b>❌ В корзине (отклонено модератором):</b>\n{item['title']}"
                )
                
            elif data.startswith("trash_"):
                item_id = int(data.split("_")[1])
                item = db.get_by_id(item_id)
                
                if not item:
                    await answer_callback_query(cb_id, "Новость не найдена!")
                    return {"status": "ok"}
                    
                await answer_callback_query(cb_id, "Удалено в мусор.")
                db.update_scoring(item_id, item["score"], item["score_reason"], status='trash')
                await edit_message_text(
                    chat_id, 
                    message_id, 
                    f"<b>🗑️ В мусоре:</b>\n{item['title']}"
                )
                
            elif data.startswith("gen_"):
                parts = data.split("_")
                generator = parts[1]  # pollinations, cloudflare, or huggingface
                target_chat_id = int(parts[2])
                
                state = test_image_states.get(target_chat_id)
                if not state or not state.get("prompt"):
                    await answer_callback_query(cb_id, "Сессия истекла. Используйте /test_image заново.")
                    return {"status": "ok"}
                
                prompt = state["prompt"]
                del test_image_states[target_chat_id]
                
                await answer_callback_query(cb_id, f"Генерирую через {generator}...")
                await edit_message_text(chat_id, message_id, f"<b>⏳ Генерирую изображение...</b>\nПромпт: {publisher._escape_html(prompt)}\nГенератор: {generator}")
                
                # Generate image
                from smm_engine.media.image_handler import ImageGenerator
                img_gen = ImageGenerator()
                img_path = None
                
                try:
                    if generator == "pollinations":
                        img_path = await img_gen.generate_pollinations_background(prompt)
                    elif generator == "cloudflare":
                        img_path = await img_gen.generate_cloudflare_background(prompt)
                    elif generator == "huggingface":
                        img_path = await img_gen.generate_hf_background(prompt)
                except Exception as exc:
                    logger.error("Test image generation failed (%s)", type(exc).__name__)
                
                if img_path and img_path.exists():
                    # Send the generated image
                    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
                    try:
                        async with httpx.AsyncClient() as client:
                            with open(img_path, "rb") as f:
                                resp = await client.post(
                                    url,
                                    data={"chat_id": chat_id, "caption": f"✅ {generator}\nПромпт: {prompt[:200]}"},
                                    files={"photo": f},
                                    timeout=45
                                )
                                if resp.status_code != 200:
                                    await send_bot_message(
                                        chat_id,
                                        "❌ Telegram отклонил тестовое изображение.",
                                    )
                    except Exception as exc:
                        logger.error(
                            "Test image delivery failed (%s)",
                            type(exc).__name__,
                        )
                        await send_bot_message(
                            chat_id,
                            "❌ Не удалось отправить тестовое изображение.",
                        )
                    finally:
                        try:
                            img_path.unlink()
                        except Exception:
                            pass
                else:
                    await send_bot_message(chat_id, f"❌ Генератор <b>{generator}</b> не смог создать изображение. Проверьте API ключи и логи.")
                
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Telegram webhook handling failed (%s)", type(exc).__name__)
        
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def dashboard_view(request: Request, username: Optional[str] = Depends(authenticate_dashboard)):
    """Renders the HTML Dashboard"""
    try:
        # Fetch stats
        stats = db.get_stats()

        is_paused = db.get_setting("is_paused", "false") == "true"
        queue_items = db.get_queue(status='pending_review', limit=15)
        rejected_items = db.get_queue(status='rejected', limit=10)
        
        chart_data = db.get_publication_stats()
        if not chart_data:
            from datetime import datetime, timedelta
            chart_data = [{"date": (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d"), "count": 0} for i in range(6, -1, -1)]
            
        chart_labels = [x["date"] for x in chart_data]
        chart_values = [x["count"] for x in chart_data]
        
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "stats": stats,
                "is_paused": is_paused,
                "queue_items": queue_items,
                "rejected_items": rejected_items,
                "chart_labels": chart_labels,
                "chart_values": chart_values
            }
        )
    except Exception as e:
        logger.error("Error loading dashboard data (%s)", type(e).__name__)
        return HTMLResponse(
            content=f"""
            <html>
                <head>
                    <title>База данных перегружена</title>
                    <meta charset="utf-8">
                    <style>
                        body {{
                            background-color: #0d0f14;
                            color: #f4f5f6;
                            font-family: sans-serif;
                            display: flex;
                            flex-direction: column;
                            align-items: center;
                            justify-content: center;
                            height: 100vh;
                            margin: 0;
                            padding: 20px;
                        }}
                        h1 {{ color: #eb5e28; margin-bottom: 10px; text-align: center; }}
                        p {{ color: #8b9bb4; max-width: 500px; text-align: center; line-height: 1.6; margin-bottom: 20px; }}
                        button {{
                            background: linear-gradient(135deg, #eb5e28, #d85724);
                            border: none;
                            color: white;
                            padding: 12px 24px;
                            border-radius: 8px;
                            cursor: pointer;
                            font-weight: bold;
                            box-shadow: 0 4px 15px rgba(235, 94, 40, 0.3);
                            transition: transform 0.2s;
                        }}
                        button:hover {{ transform: translateY(-1px); }}
                    </style>
                </head>
                <body>
                    <h1>База данных временно недоступна</h1>
                    <p>Сервис данных временно недоступен. Пожалуйста, подождите 15-30 секунд и обновите страницу.</p>
                    <button onclick="window.location.reload()">Обновить страницу 🔄</button>
                </body>
            </html>
            """,
            status_code=503
        )

class TogglePauseReq(BaseModel):
    active: bool

@app.post("/api/toggle-pause")
async def api_toggle_pause(req: TogglePauseReq, username: Optional[str] = Depends(authenticate_dashboard)):
    """API endpoint to toggle auto-publishing state"""
    # If active (checked), then is_paused is False
    db.set_setting("is_paused", "false" if req.active else "true")
    return {"status": "ok", "is_paused": not req.active}

class ModerateReq(BaseModel):
    action: str


class ConfirmActionReq(BaseModel):
    confirmed: Literal[True]

@app.post("/api/moderate/{item_id}")
async def api_moderate_item(item_id: int, req: ModerateReq, background_tasks: BackgroundTasks, username: Optional[str] = Depends(authenticate_dashboard)):
    """API endpoint to approve/reject an item from dashboard"""
    item = db.get_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
        
    if req.action == "approve":
        if item["status"] == "published":
            return {"status": "ok", "action": "already_published"}
            
        background_tasks.add_task(publish_item_background, item_id, 0, 0)
        return {"status": "ok", "action": "publishing_started"}
    elif req.action == "reject":
        db.update_scoring(item_id, item["score"], item["score_reason"], status='rejected')
        return {"status": "ok", "action": "rejected"}
    elif req.action == "trash":
        db.update_scoring(item_id, item["score"], item["score_reason"], status='trash')
        return {"status": "ok", "action": "trash"}
        
    raise HTTPException(status_code=400, detail="Invalid action")

@app.post("/api/force-pipeline")
async def api_force_pipeline(req: ConfirmActionReq, background_tasks: BackgroundTasks, username: Optional[str] = Depends(authenticate_dashboard)):
    """API endpoint to trigger pipeline execution"""
    if pipeline_running:
        raise HTTPException(status_code=409, detail="Парсинг уже запущен. Пожалуйста, подождите завершения текущего процесса.")
    background_tasks.add_task(run_pipeline_task)
    return {"status": "ok", "message": "Pipeline started"}

@app.post("/api/clear-db")
async def api_clear_db(req: ConfirmActionReq, username: Optional[str] = Depends(authenticate_dashboard)):
    """API endpoint to clear database for testing duplicate re-scraping"""
    db.clear_all_news()
    return {"status": "ok", "message": "Database cleared"}

@app.get("/api/test-models")
async def test_models(username: Optional[str] = Depends(authenticate_dashboard)):
    import google.generativeai as genai
    from smm_engine.config import GEMINI_API_KEY
    if not GEMINI_API_KEY:
        return {"error": "GEMINI_API_KEY is not configured"}
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        models = genai.list_models()
        return {"models": [m.name for m in models]}
    except Exception as exc:
        logger.warning("Model connectivity check failed (%s)", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"error": "Model connectivity check failed"},
        )

@app.post("/api/test-telegram")
async def test_telegram(username: Optional[str] = Depends(authenticate_dashboard)):
    import httpx
    from smm_engine.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        return {"error": "TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID is not configured"}
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": "🛠️ Тестовое сообщение от SMM-панели. Если вы видите это, значит права бота настроены верно!"
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=10)
            response_data = resp.json()
            if not resp.is_success or not response_data.get("ok"):
                logger.warning("Telegram connectivity check returned status %s", resp.status_code)
                return JSONResponse(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    content={"error": "Telegram connectivity check failed"},
                )
            return {"status": "ok", "status_code": resp.status_code}
    except Exception as exc:
        logger.warning("Telegram connectivity check failed (%s)", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"error": "Telegram connectivity check failed"},
        )



@app.get("/api/logs")
def get_api_logs(username: Optional[str] = Depends(authenticate_dashboard)):
    """Returns the last 100 log lines stored in memory"""
    return {"logs": memory_log_handler.get_logs()}

@app.get("/health")
@app.get("/healthz")
def health_check():
    return {"status": "healthy", "service": "smm-queue-bot"}


@app.get("/readyz")
async def readiness_check():
    try:
        database_ok = db.ping()
    except Exception as exc:
        logger.error("Database readiness check failed (%s)", type(exc).__name__)
        database_ok = False

    if not database_ok:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unavailable",
                "service": "smm-queue-bot",
                "database": "error",
            },
        )

    if not production_configuration_ready():
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unavailable",
                "service": "smm-queue-bot",
                "database": "ok",
                "configuration": "error",
            },
        )

    response = {"status": "ready", "service": "smm-queue-bot", "database": "ok"}
    if is_production_environment():
        response["configuration"] = "ok"
    return response
