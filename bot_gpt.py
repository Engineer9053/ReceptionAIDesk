import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from google_sheets import GoogleSheetsClient
from google_calendar import GoogleCalendarClient
import os

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

# Инициализация клиентов Google
sheets = GoogleSheetsClient()
calendar = GoogleCalendarClient()

@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    await message.answer("Здравствуйте! Я ReceptionAIDesk. Как могу помочь?\n"
                         "📋 /services — список услуг\n"
                         "🗓 /book — записаться на сеанс\n"
                         "📅 /my — мои записи")

@dp.message_handler(commands=["services"])
async def cmd_services(message: types.Message):
    services = sheets.list_services()
    reply = "Доступные услуги:\n" + "\n".join(f"- {s}" for s in services)
    await message.answer(reply)

@dp.message_handler(commands=["book"])
async def cmd_book_start(message: types.Message):
    # FSM: запрашиваем услугу
    await message.answer("Введите название услуги")
    # — установка состояния —

# FSM-хэндлеры для /book: получение названия, даты, времени,
# запись в календарь и лист, подтверждение пользователю

@dp.message_handler(commands=["my"])
async def cmd_my(message: types.Message):
    entries = calendar.list_for_user(message.from_user.id)
    reply = "Ваши записи:\n" + "\n".join(f"{e['summary']} — {e['start']}" for e in entries)
    await message.answer(reply)

def main():
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)

if __name__ == "__main__":
    main()