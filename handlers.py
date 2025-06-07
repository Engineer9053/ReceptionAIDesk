from telegram import Update
from telegram.ext import CommandHandler, ConversationHandler, MessageHandler, filters, CallbackContext
#from dialog_states import *
from calendar_service import check_free_slots, create_event
import datetime

ASK_DATETIME, ASK_EMAIL = range(2)

user_context = {}

def start(update: Update, context: CallbackContext):
    update.message.reply_text("Здравствуйте! Введите дату и время записи в формате YYYY-MM-DD HH:MM (UTC)")
    return ASK_DATETIME

def ask_email(update: Update, context: CallbackContext):
    user_context[update.effective_user.id] = {
        "datetime": update.message.text.strip()
    }
    update.message.reply_text("Укажите ваш email для записи")
    return ASK_EMAIL

def confirm_booking(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    email = update.message.text.strip()
    info = user_context.get(user_id, {})
    start_time = info.get("datetime")
    duration = 60  # по умолчанию 60 минут

    if not check_free_slots(start_time, duration):
        update.message.reply_text("Извините, выбранное время занято. Попробуйте другое.")
        return ConversationHandler.END

    event_link = create_event(
        summary="Запись клиента",
        description="Автоматическая запись через Telegram-бота",
        start_time=start_time,
        duration_minutes=duration,
        attendees=[email]
    )

    update.message.reply_text(f"Запись успешно создана! Ссылка на событие: {event_link}")
    return ConversationHandler.END

def setup_handlers(app):
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_DATETIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_email)],
            ASK_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_booking)],
        },
        fallbacks=[]
    )
    app.add_handler(conv_handler)