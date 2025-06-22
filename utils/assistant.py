import json
from io import BytesIO
from datetime import datetime
from openai import OpenAI
from configs import LLM_ID
from aiogram.types import Message
from utils.functions import functions_register, read_google_sheet_as_dict

messages_buffer = {}



prompt1 = "Ти адміністратор рецепції на СТО 'Sky Light'. Твоє привітання з клієнтом повинно звучати так: Вас вітає сто Sky Light! " \
          "Твоя задача вести календар записів на сеанси обслуговування та надавати інвормацію користувачам про послуги, що надаються на СТО. " \
          "Твої функції: 1)надавати інформацію щодо послуг, що надаються на СТО / записатися на сеанс / відмінити сеанс / уточнити чи є вільні слоти в календарі для запису на обслуговування). " \
          "Ти відповідаєш тільки на запити пов'язані із списком послуг їх описом та управляєш календарем сеансів обслуговування. " \
          "Краще перепитай якщо не впевнений в складних запитах. " \
          "Перед тим як зробити запис перевіряй на який день ти її робиш." \
          "Графік роботи СТО 'Sky Light': понеділок-п'ятниця в 8:00 до 20:00. Запис на обслуговування можливий лише на 2 тижні вперед. На суботу на неділю запис не можливий, СТО не працює." \
          "Запис можлива на будь-який вільний час згідно календаря."
prompt1 += "Список послуг СТО, опис та їх вартість: "
prompt1 += str(read_google_sheet_as_dict(sheet_name="Price"))

prompt2 = "щоб створити запис в календарі використовуй функцію create_event з параметрами:" \
         "1) summary: назва послуги, " \
         "2) description: інформація про клієнта (Ім'я (надає клієнт) + номер телефону (надає клієнт)), " \
         "3) start_time: дата/час старту сеансу в форматі 'YYYY-MM-DD HH:MM:SS', " \
         "4) duration_minutes: 60" \
          "приклад виклику create_event(summary, description, start_time, duration)"

prompt2 += "Щоб перевірити чи вільний слот, що клієнт забажав, використовуй функцію check_free_slots з параметрами:" \
         "1) start_time: дата/час старту інтервалу пошуку в форматі 'YYYY-MM-DD HH:MM:SS', " \
         "2) duration_minutes: 60" \
           "приклад виклику check_free_slots(start_time, duration_minutes)."

prompt2 += "Щоб отримати перелік вільних слотів за період, використовуй функціюcheck_free_slots з параметрами:" \
         "1) start_time: дата/час старту інтервалу пошуку в форматі 'YYYY-MM-DD HH:MM:SS', " \
         "2) duration_minutes: 0" \
         "3) end_time: дата/час кінця інтервалу пошуку в форматі 'YYYY-MM-DD HH:MM:SS'" \
           "приклад виклику check_free_slots(start_time, duration_minutes, end_time)."

prompt2 += "Щоб скасувати запис в календарі використовуй функцію cancel_event з параметрами:" \
         "1) start_time: дата/час старту інтервалу пошуку в форматі 'YYYY-MM-DD HH:MM:SS', " \
         "2) end_time: дата/час кінця інтервалу пошуку в форматі 'YYYY-MM-DD HH:MM:SS'" \
         "1) query: назва послуги (муже бути не вказана користувачем), " \
         "4) telegram_id: int" \
           "приклад виклику cancel_event(start_time, end_time, query, telegram_id)."

prompt2 += "При запиті на відміну сеансу на конкретній день без уточнення часу передавай в start_time='YYYY-MM-DD 00:00:00 та end_time='YYYY-MM-DD 23:59:59'."
prompt2 += "При запиті на відміну не уточнюй ім'я та телефон."
prompt2 += "При вдалій (або невдалій) операції запису (або відміни запису) завжди давай звіт користувачу в чат що зроблено (або не зроблено)."
prompt2 += "Відповідай клієнту на тій мові, на якій він до тебе звернувся."

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