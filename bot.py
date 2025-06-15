import logging
import asyncio
from aiogram import Bot, Dispatcher
from configs import TELEGRAM_TOKEN
from utils.database import initialize_database
from handlers.messages import router as messages_router
from handlers.commands import router as commands_router



logging.basicConfig(level=logging.INFO)


bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()


async def main() -> None:

    initialize_database()

    dp.include_router(commands_router)
    dp.include_router(messages_router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":

    asyncio.run(main())