import json
from io import BytesIO
from datetime import datetime
from openai import OpenAI
from configs import LLM_ID
from aiogram.types import Message
from utils.functions import functions_register, read_google_sheet_as_dict

messages_buffer = {}



prompt1 = "Ти адміністратор рецепції на СТО 'Sky'. Твоє привітання з клієнтом повинно звучати так: Вас вітає сто Sky! " \
          "Твоя задача вести календар записів на сеанси обслуговування та надавати інвормацію користувачам про послуги, що надаються на СТО. " \
          "Твої функції: 1)надавати інформацію щодо послуг, що надаються на СТО / записатися на сеанс / відмінити сеанс / уточнити чи є вільні слоти в календарі для запису на обслуговування). " \
          "Ти відповідаєш тільки на запити пов'язані із списком послуг їх описом та управляєш календарем сеансів обслуговування. " \
          "Краще перепитай якщо не впевнений в складних запитах. "
prompt1 += "Список послуг СТО, опис та їх вартість: "
prompt1 += str(read_google_sheet_as_dict(sheet_name="Price"))

prompt2 = "Для роботи з календарем в тебе є такі функції:" \
          " 1. Щоб створити запис в календарі використовуй функцію create_event(summary, description, start_time, duration_minutes=60). " \
          "1.1. summary: str (назва послуги) " \
          "1.2. description: str (інформація про клієнта (Ім'я (надає клієнт) + номер телефону (надає клієнт))) " \
          "1.3. start_time: str (дата/час старту сеансу в форматі 'YYYY-MM-DD HH:MM:SS') " \
          "1.4. duration_minutes: int (дефолтне значення - 60) "

prompt2 += "2. Якщо клієнт надає бажаний час для запису, то перед викликом функції create_event тобі потрібно перевірити, чи вільний цей час в календарі. " \
           "Щоб перевірити чи вільний слот, що клієнт забажав, використовуй функцію check_free_slots(start_time, duration_minutes=60). " \
           "2.1 start_time: str (дата/час старту інтервалу пошуку в форматі 'YYYY-MM-DD HH:MM:SS') " \
           "2.2 duration_minutes: int (дефолтне значення - 60)"

prompt2 += "3. Якщо клієнт запитує про наявність вільних слотів для запису, використовуй функцію check_free_slots(start_time, duration_minutes=0, end_time). " \
           "При такому виклику у відповідь функція поверне перелік вільних слотів у форматі списку. Приклад:" \
           "['2025-06-23 08:00 - 2025-06-23 10:00', '2025-06-23 11:00 - 2025-06-23 14:00']. Ти повинен зробити цей список у форматі '1. ... 2. ... 3. ...' і кожен пункт з нового рядку " \
           "3.1. start_time: str (дата/час старту інтервалу пошуку в форматі 'YYYY-MM-DD HH:MM:SS') " \
           "3.2. duration_minutes: int (дефолтне значення - 0) " \
           "3.3. end_time: str (дата/час кінця інтервалу пошуку в форматі 'YYYY-MM-DD HH:MM:SS') "

prompt2 += "4. Щоб скасувати запис в календарі використовуй функцію cancel_event(start_time, end_time, query, telegram_id). " \
           "4.1. start_time: str (дата/час старту інтервалу пошуку в форматі 'YYYY-MM-DD HH:MM:SS') " \
           "4.2. end_time: str (дата/час кінця інтервалу пошуку в форматі 'YYYY-MM-DD HH:MM:SS') " \
           "4.3. query: str (назва послуги (муже бути не вказана користувачем)) " \
           "4.4. telegram_id: int "

prompt2 += "При запиті на відміну сеансу на конкретній день без уточнення часу передавай в start_time='YYYY-MM-DD 00:00:00 та end_time='YYYY-MM-DD 23:59:59'. "
prompt2 += "При запиті на відміну не уточнюй ім'я та телефон. "
prompt2 += "При вдалій (або невдалій) операції запису (або відміни запису) завжди давай звіт користувачу в чат що зроблено (або не зроблено). "
prompt2 += "Відповідай клієнту на тій мові, на якій він до тебе звернувся. "

now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

functions = [
    {
        "type": "function",
        "function": {
            "name": "create_event",
            "description": "Функція що виконує запис користувача на сеанс.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Назва послуги"
                    },
                    "description": {
                        "type": "string",
                        "description": "Інформація про клієнта (Ім'я + номер телефону клієнта)"
                    },
                    "start_time": {
                        "type": "string",
                        "description": f"Дата та час сеансу",
                    },
                    "duration_minutes": {
                        "type": "number",
                        "description": "Тривалість сеансу."
                    },
                    "telegram_id": {
                        "type": "string",
                        "description": f"telegram_id клієнта",
                    }
                },
                "required": ["summary", "description", "start_time", "duration_minutes"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_event",
            "description": "Функція що відміняє запис користувача на сеанс.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_time_local": {
                        "type": "string",
                        "description": f"Дата початку пошуку у форматі 'YYYY-MM-DD HH:MM:SS'",
                    },
                    "end_time_local": {
                        "type": "string",
                        "description": f"Дата кінця пошуку у форматі 'YYYY-MM-DD HH:MM:SS'",
                    },
                    "telegram_id": {
                        "type": "string",
                        "description": f"telegram_id клієнта",
                    },
                    "duration_minutes": {
                        "type": "number",
                        "description": "Тривалість сеансу."
                    },
                    "user_timezone": {
                        "type": "string",
                        "description": f"Часовий пояс у форматі 'Europe/Kyiv'",
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_free_slots",
            "description": "Функція що повертає вільні слоти за вказаний період в календарі.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_time": {
                        "type": "string",
                        "description": f"Дата початку пошуку у форматі 'YYYY-MM-DD HH:MM:SS'",
                    },
                    "duration_minutes": {
                        "type": "number",
                        "description": "Тривалість сеансу."
                    },
                    "end_time": {
                        "type": "string",
                        "description": f"Дата кінця пошуку у форматі 'YYYY-MM-DD HH:MM:SS'",
                    },
                    "user_timezone": {
                        "type": "string",
                        "description": f"Часовий пояс у форматі 'Europe/Kyiv'",
                    }
                }
            }
        }
    }
]


def text_assistant(message: Message, client: OpenAI) -> str:

    telegram_id = message.from_user.id
    text = message.text

    if telegram_id not in messages_buffer:

        messages_buffer[telegram_id] = []
    
    messages_buffer[telegram_id].append(
        {
            "role": "user",
            "content": text
        }
    )

    response = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": f"{prompt1}. {prompt2}. Поточна дата/час: {now}."
            }
        ] + messages_buffer[telegram_id],
        model=LLM_ID,
        tools=functions
    )

    ai_message = response.choices[0].message
    messages_buffer[telegram_id].append(ai_message)

    if ai_message.content:

        return ai_message.content
    
    if ai_message.tool_calls:

        results = []

        for tool_call in ai_message.tool_calls:

            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)
            tool_args["telegram_id"] = telegram_id

            result = functions_register[tool_name](**tool_args)

            results.append(result)

            messages_buffer[telegram_id].append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                }
            )
        
        return "\n\n".join(results)


def audio_assistant(message: Message, audio_text: str, client: OpenAI) -> str:

    telegram_id = message.from_user.id
    text = audio_text

    if telegram_id not in messages_buffer:

        messages_buffer[telegram_id] = []
    
    messages_buffer[telegram_id].append(
        {
            "role": "user",
            "content": text
        }
    )

    response = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": f"{prompt1}. {prompt2}. Поточна дата/час: {now}. "
            }
        ] + messages_buffer[telegram_id],
        model=LLM_ID,
        tools=functions
    )

    ai_message = response.choices[0].message
    messages_buffer[telegram_id].append(ai_message)

    if ai_message.content:

        return ai_message.content
    
    if ai_message.tool_calls:

        results = []

        for tool_call in ai_message.tool_calls:

            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)
            tool_args["telegram_id"] = telegram_id

            result = functions_register[tool_name](**tool_args)

            results.append(result)

            messages_buffer[telegram_id].append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                }
            )
        
        return "\n\n".join(results)