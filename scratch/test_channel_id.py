import os
from dotenv import load_dotenv
load_dotenv()
print("TELEGRAM_BOT_TOKEN:", os.getenv("TELEGRAM_BOT_TOKEN"))
print("TELEGRAM_CHANNEL_ID:", os.getenv("TELEGRAM_CHANNEL_ID"))
