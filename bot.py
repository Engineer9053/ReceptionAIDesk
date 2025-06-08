from telegram.ext import ApplicationBuilder
from config import TELEGRAM_TOKEN
from handlers import setup_handlers

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
setup_handlers(app)
app.run_polling()