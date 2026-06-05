import logging
import asyncio
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import httpx

from smm_engine.config import TELEGRAM_BOT_TOKEN
from smm_engine.storage.database import DatabaseManager
from smm_engine.publishers.telegram_pub import TelegramPublisher
from smm_engine.pipeline import SMMPipeline

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telegram_bot")

app = FastAPI(title="SMM Automator Queue Bot")
db = DatabaseManager()
publisher = TelegramPublisher()
templates = Jinja2Templates(directory="web/templates")

# State variables to prevent concurrent pipeline runs
pipeline_running = False
pipeline_lock = asyncio.Lock()

@app.on_event("startup")
async def startup_event():
    """Auto-registers Telegram Webhook on startup using Render URL"""
    import os
    render_url = os.getenv("RENDER_EXTERNAL_URL")
    if render_url and TELEGRAM_BOT_TOKEN:
        webhook_url = f"{render_url}/webhook"
        set_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(set_url, json={"url": webhook_url}, timeout=10)
                logger.info(f"Auto-setting Telegram Webhook to {webhook_url}: {resp.json()}")
        except Exception as e:
            logger.error(f"Failed to auto-set Telegram Webhook on startup: {e}")

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
    except Exception as e:
        logger.error(f"Error sending bot message: {e}")

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
    except Exception as e:
        logger.error(f"Error answering callback: {e}")

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
    except Exception as e:
        logger.error(f"Error editing message: {e}")

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
    except Exception as e:
        logger.error(f"Error in manual pipeline execution: {e}")
    finally:
        async with pipeline_lock:
            pipeline_running = False

@app.post("/webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    """Main webhook endpoint for Telegram Bot Updates"""
    try:
        update = await request.json()
        logger.info(f"Received update: {update}")
        
        # 1. Handle commands/text messages
        if "message" in update:
            message = update["message"]
            chat_id = message["chat"]["id"]
            text = message.get("text", "")
            
            if text == "/start":
                welcome = (
                    "<b>Привет! Я бот управления SMM Автоматизатором.</b>\n\n"
                    "Команды:\n"
                    "/status — Статистика и состояние системы\n"
                    "/queue — Очередь постов на модерацию\n"
                    "/pause — Приостановить автопубликацию (все посты в очередь)\n"
                    "/resume — Включить автопубликацию (85+ сразу в канал)\n"
                    "/force — Запустить парсинг и публикацию вручную"
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
                
        # 2. Handle callback queries from buttons
        elif "callback_query" in update:
            cb = update["callback_query"]
            cb_id = cb["id"]
            chat_id = cb["message"]["chat"]["id"]
            message_id = cb["message"]["message_id"]
            data = cb.get("data", "")
            
            if data.startswith("approve_"):
                item_id = int(data.split("_")[1])
                item = db.get_by_id(item_id)
                
                if not item:
                    await answer_callback_query(cb_id, "Новость не найдена в базе!")
                    return {"status": "ok"}
                    
                await answer_callback_query(cb_id, "Публикую...")
                
                # Publish
                success = await publisher.publish_post_with_cover(item["adapted_title"], item["adapted_text"])
                if success:
                    # Also publish to Threads
                    from smm_engine.publishers.threads_pub import ThreadsPublisher
                    threads_pub = ThreadsPublisher()
                    await threads_pub.publish_post(f"{item['adapted_title']}\n\n{item['adapted_text']}")
                    
                    db.mark_published(item_id)
                    await edit_message_text(
                        chat_id, 
                        message_id, 
                        f"<b>✅ Опубликовано в канал:</b>\n{item['adapted_title']}"
                    )
                else:
                    await send_bot_message(chat_id, "❌ Ошибка при отправке сообщения в канал.")
                    
            elif data.startswith("reject_"):
                item_id = int(data.split("_")[1])
                item = db.get_by_id(item_id)
                
                if not item:
                    await answer_callback_query(cb_id, "Новость не найдена!")
                    return {"status": "ok"}
                    
                await answer_callback_query(cb_id, "Отклонено.")
                db.update_scoring(item_id, item["score"], item["score_reason"], status='rejected')
                await edit_message_text(
                    chat_id, 
                    message_id, 
                    f"<b>❌ Отклонено модератором:</b>\n{item['title']}"
                )
                
    except Exception as e:
        logger.error(f"Error handling webhook: {e}", exc_info=True)
        
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def dashboard_view(request: Request):
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
        import traceback
        import html
        error_details = traceback.format_exc()
        logger.error(f"Error loading dashboard data: {e}\n{error_details}")
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
                        pre {{
                            background: #1c2333;
                            color: #ffb703;
                            padding: 15px;
                            border-radius: 8px;
                            max-width: 85%;
                            overflow-x: auto;
                            font-size: 12px;
                            margin-top: 30px;
                            text-align: left;
                            border-left: 4px solid #d90429;
                            white-space: pre-wrap;
                            word-break: break-all;
                        }}
                    </style>
                </head>
                <body>
                    <h1>База данных временно недоступна</h1>
                    <p>Похоже, к базе данных выполняется слишком много одновременных подключений из-за частых запросов парсинга. Пожалуйста, подождите 15-30 секунд и обновите страницу.</p>
                    <button onclick="window.location.reload()">Обновить страницу 🔄</button>
                    <pre><b>Детали ошибки для разработчика:</b><br><br>{html.escape(error_details)}</pre>
                </body>
            </html>
            """,
            status_code=503
        )

class TogglePauseReq(BaseModel):
    active: bool

@app.post("/api/toggle-pause")
async def api_toggle_pause(req: TogglePauseReq):
    """API endpoint to toggle auto-publishing state"""
    # If active (checked), then is_paused is False
    db.set_setting("is_paused", "false" if req.active else "true")
    return {"status": "ok", "is_paused": not req.active}

class ModerateReq(BaseModel):
    action: str

@app.post("/api/moderate/{item_id}")
async def api_moderate_item(item_id: int, req: ModerateReq):
    """API endpoint to approve/reject an item from dashboard"""
    item = db.get_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
        
    if req.action == "approve":
        title = item["adapted_title"]
        text = item["adapted_text"]
        
        # If it failed to adapt earlier (None or literal 'None' string), let's adapt it on the fly now!
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
            news_item = NewsItem(
                source=item["source"],
                source_id=item["source_id"],
                title=item["title"],
                url=item["url"],
                raw_data={}
            )
            try:
                adapted = await adapter.adapt_news(news_item)
                if adapted and adapted.get("title") and adapted.get("text"):
                    title = adapted["title"]
                    text = adapted["text"]
                    
                    if title.strip().lower() == "none" or text.strip().lower() == "none":
                        raise Exception("Adapter returned literal 'None' string")
                        
                    # Save it so we don't have to re-adapt next time
                    db.save_adapted_content(item_id, title, text, status=item["status"])
                else:
                    raise Exception("Adapter returned empty content")
            except Exception as ex:
                logger.error(f"Failed to adapt item {item_id} on the fly: {ex}")
                # Fallback to original title and url
                title = item["title"]
                text = f"<b>{item['title']}</b>"
                
        success = await publisher.publish_post_with_cover(title, text)
        if success:
            # Also publish to Threads
            from smm_engine.publishers.threads_pub import ThreadsPublisher
            threads_pub = ThreadsPublisher()
            await threads_pub.publish_post(f"{title}\n\n{text}")
            
            db.mark_published(item_id)
            return {"status": "ok", "action": "approved"}
        else:
            raise HTTPException(status_code=500, detail="Telegram publishing failed")
    elif req.action == "reject":
        db.update_scoring(item_id, item["score"], item["score_reason"], status='rejected')
        return {"status": "ok", "action": "rejected"}
        
    raise HTTPException(status_code=400, detail="Invalid action")

@app.post("/api/force-pipeline")
async def api_force_pipeline(background_tasks: BackgroundTasks):
    """API endpoint to trigger pipeline execution"""
    global pipeline_running
    if pipeline_running:
        raise HTTPException(status_code=409, detail="Парсинг уже запущен. Пожалуйста, подождите завершения текущего процесса.")
    background_tasks.add_task(run_pipeline_task)
    return {"status": "ok", "message": "Pipeline started"}

@app.get("/api/test-models")
async def test_models():
    import google.generativeai as genai
    from smm_engine.config import GEMINI_API_KEY
    if not GEMINI_API_KEY:
        return {"error": "GEMINI_API_KEY is not configured"}
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        models = genai.list_models()
        return {"models": [m.name for m in models]}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/test-telegram")
async def test_telegram():
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
            return {
                "status_code": resp.status_code,
                "response": resp.json()
            }
    except Exception as e:
        return {"error": str(e)}

@app.get("/health")
@app.get("/healthz")
def health_check():
    return {"status": "healthy", "service": "smm-queue-bot"}
