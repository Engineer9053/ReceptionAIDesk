from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from utils.database import insert_into_users, select_from_users



router = Router()


@router.message(Command("start"))
async def command_start_handler(message: Message) -> None:

    user = {
        "telegram_id": message.from_user.id,
        "first_name": message.from_user.first_name or "Unknown",
        "last_name": message.from_user.last_name or "Unknown",
        "username": message.from_user.username or "Unknown"
    }

    if user["telegram_id"] in [user["telegram_id"] for user in select_from_users()]:

        await message.answer("Вітаю!\bРадий знову Вас бачити!\nЧим можу допомогти.")
    
    else:

        insert_into_users(user)

        await message.answer("Вітаю!\bЦе рецепція СТО, чим можу Вам допомогти?.")