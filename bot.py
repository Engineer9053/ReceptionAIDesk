# import logging
# import asyncio
# from aiogram import Bot, Dispatcher
# from config import BOT_TOKEN
# from utils.database import initialize_database
# from handlers.commands import router as commands_router
# from handlers.messages import router as messages_router
# 
# 
# 
# logging.basicConfig(level=logging.INFO)
# 
# 
# bot = Bot(token=BOT_TOKEN)
# dp = Dispatcher()
# 
# 
# async def main() -> None:
# 
#     initialize_database()
# 
#     dp.include_router(commands_router)
#     dp.include_router(messages_router)
# 
#     await bot.delete_webhook(drop_pending_updates=True)
#     await dp.start_polling(bot)
# 
# 
# if __name__ == "__main__":
# 
#     asyncio.run(main())
    
    
    
from telegram.ext import ApplicationBuilder
from config import TELEGRAM_TOKEN
from handlers import setup_handlers

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
setup_handlers(app)
app.run_polling()