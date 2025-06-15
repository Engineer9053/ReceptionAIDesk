import uuid
import base64
from io import BytesIO
from openai import OpenAI
from configs import OPENAI_API_KEY, LLM_ID, AUDIO_LLM
from aiogram import Router, F
from aiogram.types import Message
from aiogram.types import BufferedInputFile
from utils.assistant import text_assistant, audio_assistant
from aiogram import Bot, Dispatcher, types



router = Router()

client = OpenAI(api_key=OPENAI_API_KEY)

@router.message(commands=["start"])
async def cmd_start(message: types.Message):
    await message.answer("Здравствуйте! Я ReceptionAIDesk. Как могу помочь?\n"
                         "📋 /services — список услуг\n"
                         "🗓 /book — записаться на сеанс\n"
                         "📅 /my — мои записи")

# @router.message(commands=["services"])
# async def cmd_services(message: types.Message):
#     services = sheets.list_services()
#     reply = "Доступные услуги:\n" + "\n".join(f"- {s}" for s in services)
#     await message.answer(reply)


@router.message(commands=["book"])
async def cmd_book_start(message: types.Message):
    # FSM: запрашиваем услугу
    await message.answer("Введите название услуги")
    # — установка состояния —

# FSM-хэндлеры для /book: получение названия, даты, времени,
# запись в календарь и лист, подтверждение пользователю


# @router.message(commands=["my"])
# async def cmd_my(message: types.Message):
#     entries = calendar.list_for_user(message.from_user.id)
#     reply = "Ваши записи:\n" + "\n".join(f"{e['summary']} — {e['start']}" for e in entries)
#     await message.answer(reply)
@router.message(F.text)
async def message_text_handler(message: Message) -> None:

    response = text_assistant(message, client)

    if isinstance(response, str):

        await message.answer(response)
    
    elif isinstance(response, BytesIO):

        await message.answer_photo(BufferedInputFile(response.read(), filename=f"{uuid.uuid4().hex}.png"), caption="Какой-то текст.")

@router.message(F.voice | F.audio)
async def handle_audio(message: Message):
    
    audio = message.voice if message.voice else message.audio

    file = await message.bot.get_file(audio.file_id)
    file_stream = await message.bot.download_file(file.file_path)
    file_stream.seek(0)

    ogg_file = ("audio.ogg", file_stream, "audio/ogg")

    response = client.audio.transcriptions.create(
        model=AUDIO_LLM,
        file=ogg_file
    )

    audio_text = response.text

    response = audio_assistant(message, audio_text, client)

    if isinstance(response, str):

        await message.answer(response)
    
    elif isinstance(response, BytesIO):

        await message.answer_photo(BufferedInputFile(response.read(), filename=f"{uuid.uuid4().hex}.png"), caption="Какой-то текст.")