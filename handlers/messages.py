import uuid
import asyncio
from io import BytesIO
from openai import OpenAI
from configs import OPENAI_API_KEY, AUDIO_LLM
from aiogram import Router, F
from aiogram.types import Message
from aiogram.types import BufferedInputFile
from utils.assistant import text_assistant, audio_assistant

router = Router()
# user_id -> {"messages": [str], "task": asyncio.Task}
user_sessions = {}

client = OpenAI(api_key=OPENAI_API_KEY)

class FakeMessage:
    def __init__(self, original_message: Message, new_text: str):
        self.from_user = original_message.from_user
        self.chat = original_message.chat
        self.message_id = original_message.message_id
        self.text = new_text
        self.bot = original_message.bot


async def delayed_batch_send(user_id: int, message: Message):
    try:
        await asyncio.sleep(10)

        all_messages = user_sessions[user_id]["messages"]
        full_prompt = "\n".join(all_messages)

        mock_message = FakeMessage(message, full_prompt)

        response = text_assistant(mock_message, client)

        if isinstance(response, str):
            await message.answer(response)
        elif isinstance(response, BytesIO):
            await message.answer_photo(
                BufferedInputFile(response.read(), filename=f"{uuid.uuid4().hex}.png"),
                caption="Какой-то текст."
            )

        user_sessions.pop(user_id, None)

    except asyncio.CancelledError:
        pass


@router.message(F.text)
async def message_text_handler(message: Message) -> None:
    user_id = message.from_user.id
    text = message.text

    # Создаём сессию, если нет
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            "messages": [],
            "task": None
        }

    # Добавляем сообщение в очередь
    user_sessions[user_id]["messages"].append(text)

    # Перезапускаем таймер, если задача уже была
    if user_sessions[user_id]["task"]:
        user_sessions[user_id]["task"].cancel()

    # Запускаем новую задачу ожидания
    user_sessions[user_id]["task"] = asyncio.create_task(
        delayed_batch_send(user_id, message)
    )


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

    # ВАЖНО: если audio_assistant — sync-функция, НЕ await
    response = audio_assistant(message, audio_text, client)

    if isinstance(response, str):
        await message.answer(response)

    elif isinstance(response, BytesIO):
        await message.answer_photo(
            BufferedInputFile(response.read(), filename=f"{uuid.uuid4().hex}.png"),
            caption="Какой-то текст."
        )
