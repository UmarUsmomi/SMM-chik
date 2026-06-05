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
    """Manually triggers the SMM pipeline in background"""
    logger.info("Manual pipeline run triggered via bot...")
    pipeline = SMMPipeline()
    await pipeline.run()

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
                    msg = (
                        f"<b>🔥 Новость в очереди (ID: {item['id']})</b>\n"
                        f"<b>Источник:</b> {item['source']}\n"
                        f"<b>Оригинальный заголовок:</b> {item['title']}\n"
                        f"<b>Скоринг:</b> {item['score']}/100\n"
                        f"<b>Почему:</b> {item['score_reason']}\n\n"
                        f"--- <b>ПРЕВЬЮ ПОСТА</b> ---\n"
                        f"<b>{item['adapted_title']}</b>\n\n"
                        f"{item['adapted_text']}"
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
                success = await publisher.publish_text(item["adapted_title"], item["adapted_text"])
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
    # Fetch stats
    stats = db.get_stats()

    is_paused = db.get_setting("is_paused", "false") == "true"
    queue_items = db.get_queue(status='pending_review', limit=15)
    
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
            "chart_labels": chart_labels,
            "chart_values": chart_values
        }
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
        success = await publisher.publish_text(item["adapted_title"], item["adapted_text"])
        if success:
            # Also publish to Threads
            from smm_engine.publishers.threads_pub import ThreadsPublisher
            threads_pub = ThreadsPublisher()
            await threads_pub.publish_post(f"{item['adapted_title']}\n\n{item['adapted_text']}")
            
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
    background_tasks.add_task(run_pipeline_task)
    return {"status": "ok", "message": "Pipeline started"}

@app.get("/health")
@app.get("/healthz")
def health_check():
    return {"status": "healthy", "service": "smm-queue-bot"}
