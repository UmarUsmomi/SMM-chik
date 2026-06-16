import asyncio
import sys
from smm_engine.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID
from smm_engine.publishers.telegram_pub import TelegramPublisher

async def main():
    print(f"BOT_TOKEN: {TELEGRAM_BOT_TOKEN}")
    print(f"CHANNEL_ID: {TELEGRAM_CHANNEL_ID}")
    
    pub = TelegramPublisher()
    title = "Test Bold Title 🚀"
    text = "This is a <b>test</b> of <i>HTML</i> formatting and <blockquote expandable>collapsible blockquote</blockquote>."
    
    # Test sending text
    success = await pub.publish_text(title, text)
    print(f"publish_text success: {success}")

if __name__ == "__main__":
    asyncio.run(main())
