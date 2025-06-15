import json
from io import BytesIO
from datetime import datetime
from openai import OpenAI
from configs import LLM_ID
from aiogram.types import Message
from utils.functions import functions_register, read_google_sheet_as_dict

messages_buffer = {}

prompt1 = "Ти адміністратор на СТО. Твоя задача отримувати вести календар записів на сеанси обслуговування та надавати інвормацію юзерам про послуги, що надаються на СТО. " \
          "Ти повинен розпізнавати що саме необхадно користувачу (отримати інформацію щодо послуг / записатися на сеанс / відмінити сеанс / уточнити чи є вільні слоти в календарі для запису на обслуговування) " \
          "та виконувати відповідний функціонал. Ти відповідаєш тільки на запити пов'язані із списком послуг їх описом та управляєш календарем сеансів обслуговування.  " \
          "Краще перепитай якщо не впевнений в складних запитах. Якщо запис можливий лише на пн-пт з 9:00 до 19:00. Запис можлива хоч на зараз, якщо є вільне місцев календарі"

prompt2 = "При виборі функції create_event використовуй такі параметри :" \
         "1) summary: назва послуги, " \
         "2) description: інформація про клієнта (Ім'я (надає клієнт) + номер телефону (надає клієнт)), " \
         "3) start_time: дата/час старту сеансу в форматі 'YYYY-MM-DD HH:MM:SS', " \
         "4) duration_minutes: 60" \
          "приклад виклику create_event(summary, description, start_time, duration)"

prompt2 += "При виборі функції cancel_event використовуй такі параметри :" \
         "1) start_time: дата/час старту інтервалу пошуку в форматі 'YYYY-MM-DD HH:MM:SS', " \
         "2) end_time: дата/час кінця інтервалу пошуку в форматі 'YYYY-MM-DD HH:MM:SS'" \
         "1) query: назва послуги (муже бути не вказана користувачем), " \
         "4) telegram_id: int" \
           "приклад виклику cancel_event(start_time, end_time, query, telegram_id)"

prompt2 += "При запиті на відміну сеансу на конкретній день без уточнення часу передавай в start_time='YYYY-MM-DD 00:00:00 та end_time='YYYY-MM-DD 23:59:59'."
prompt2 += "При запиті на відміну не уточнюй ім'я та телефон."
prompt2 += "При вдалій (або невдалій) операції запису (або відміни запису) завжди давай звіт користувачу в чат що зроблено (або не зроблено)."



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
                    "user_timezone": {
                        "type": "string",
                        "description": f"Часовий пояс у форматі 'Europe/Kyiv'",
                    },
                    "query": {
                        "type": "string",
                        "description": "Ключові слова опису події."
                    },
                    "telegram_id": {
                        "type": "number",
                        "description": "telegram_id користувача."
                    }
                }
            }
        }
    }
]


def text_assistant(message: Message, client: OpenAI) -> str:

    telegram_id = message.from_user.id
    text = message.text
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #categories = [category["category"] for category in select_from_categories()]
    categories = read_google_sheet_as_dict(sheet_name="Price")

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
                "content": f"{prompt1}. Поточна дата/час: {now}.{prompt2}."
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

            if isinstance(result, BytesIO):

                messages_buffer[telegram_id].append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": "Виведена статистика за вказаними параметрами."
                    }
                )

                return result

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
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    categories = [category["category"] for category in select_from_categories()]

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
                "content": f"{prompt1}. Поточна дата/час: {now}.{prompt2}."
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

            if isinstance(result, BytesIO):

                messages_buffer[telegram_id].append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": "Виведена статистика за вказаними параметрами."
                    }
                )

                return result

            results.append(result)

            messages_buffer[telegram_id].append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                }
            )
        
        return "\n\n".join(results)