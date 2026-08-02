import os
from dotenv import load_dotenv
load_dotenv()
print("TELEGRAM_BOT_TOKEN configured:", bool(os.getenv("TELEGRAM_BOT_TOKEN")))
print("TELEGRAM_CHANNEL_ID configured:", bool(os.getenv("TELEGRAM_CHANNEL_ID")))
