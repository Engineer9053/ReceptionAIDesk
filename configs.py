import os
from dotenv import load_dotenv
load_dotenv()

TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")
print("GOOGLE_CREDENTIALS_JSON loaded:", os.getenv("GOOGLE_CREDENTIALS_JSON")[:100])
CALENDAR_ID = os.getenv("CALENDAR_ID")
CALENDAR_ID_USER = os.getenv("CALENDAR_ID_USER")
SHEET_ID = os.getenv("SHEET_ID")
DATABASE_PATH = "database.db"
LLM_ID = "gpt-4o"
AUDIO_LLM = "whisper-1"