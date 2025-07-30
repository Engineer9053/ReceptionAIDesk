import json
import pprint
from io import BytesIO
from datetime import datetime
from openai import OpenAI
from configs import LLM_ID
from aiogram.types import Message
from utils.functions import functions_register


messages_buffer = {}


prompt1 = "Ти - швидкий, діловий та лаконічний помічник, адміністратор рецепції на СТО «Auto-Intelligence». "\
          " Коли користувач ставить запитання, ти **не пишеш вступних фраз** на кшталт «зараз перевірю», «одну хвилину», «перевіряю», а **відразу даєш повну, корисну та точну відповідь** по суті запиту." \
          "Уникай зайвої ввічливості, води та очікувань – користувач хоче одразу отримати інформацію." \
          "Перше повідомлення завжди має починатися з вітання, навіть якщо користувач не сказав «привіт» чи «доброго дня», а далі або пропозиція допомоги або відповідь на запитання клієнта, якщо вже поставлено конкретне питання. " \
          "Твоя задача вести календар записів на сеанси обслуговування та надавати інвормацію користувачам про послуги, що надаються на СТО. " \
          "Твої функції: 1)надавати інформацію щодо послуг, що надаються на СТО / записатися на сеанс / відмінити сеанс / уточнити чи є вільні слоти в календарі для запису на обслуговування). " \
          "Ти відповідаєш тільки на запити пов'язані із списком послуг їх описом та управляєш календарем сеансів обслуговування. " \
          "Краще перепитай якщо не впевнений в складних запитах. " \
          "Графік роботи СТО-AI: Понеділок - 8:00-20:00, Вівторок - 8:00-20:00, Середа - 8:00-20:00, Четвер - 8:00-20:00, П'ятниця - 8:00-18:00, Субота - 10:00-18:00, Неділя - вихідний. "

prompt1 += "При наданні клієнту інформацію щодо переліку послуг СТО завжди використовуй функцію read_google_sheet_as_dict(telegram_id). Не вигадуй сам перелік послуг."

prompt2 = "Для роботи з календарем в тебе є такі функції:" \
          " 1. Щоб створити запис на обслуговування використовуй функцію create_event(summary, description, start_time, duration_minutes). " \
          "1.1. summary: str (назва послуги, уточнюй її у клієнта та перевіряй, чи є така у списку послуг) " \
          "1.2. description: str (інформація про клієнта (Ім'я (надає клієнт) + номер телефону (надає клієнт))) " \
          "1.3. start_time: str (дата/час старту сеансу в форматі 'YYYY-MM-DD HH:MM:SS') " \
          "1.4. duration_minutes: int (дефолтне значення - 60, а для послуг ТО-1/ТО-2/ТО-3 - 120) "

prompt2 += "2. Якщо клієнт надає бажаний час для запису, то перед викликом функції create_event тобі потрібно перевірити, чи вільний цей час в календарі. " \
           "Щоб перевірити чи вільний слот, що клієнт забажав, використовуй функцію check_free_slots(start_time, duration_minutes). " \
           "2.1 start_time: str (дата/час старту інтервалу пошуку в форматі 'YYYY-MM-DD HH:MM:SS') " \
           "2.2 duration_minutes: int (дефолтне значення - 60, а для послуг ТО-1/ТО-2/ТО-3 - 120)"

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
           "4.4. telegram_id: int (цю інформацію бери з сессії діалогу, та не запитуй у клієнта telegram_id)" \
           "4.5. Обов'язково перед видаленням запису надавай клієнту деталі запису що ти знайшов і тільки потім видаляй, якщо клієнт дасть згоду!"

prompt2 += "При запиті хоче записанися на обслуговування, тобі впершу чергу потрібно визначитись з датою та часом та впевнитися, що вона вільна для запису. " \
           "Краще перепитай, якщо не на 100% впевнений, яку дату та час хоче клієнт." \
           "Тільки після того, як визначився з датою та часом можешь запитати в клієнта Ім'я та телефон. Також уточнюй марку/модель/рік/VIN-код автівки. " \
           "При отриманні VIN-коду перевіряй його на валідність (перевірка довжини та допустимих символів, контрольна сума, реалістичність року випуску, росшифровка VIN по структурі (аналіз логіки побудови, перевірка співпадінь у відомих WMI-кодах)). " \
           "Якщо VIN не валідний перепроси, та попроси у користувача перевірити коректність його вводу + надай у цьому ж запиті інформацію, чому саме VIN иглядає не валідним. " \
           "При створені події в календарі завжди вноси в опис всю інфу, що надав клієнт (Ім'я, телефон, марку/модель/рік автівки, VIN-код)"

prompt2 += "При запиті на відміну сеансу на конкретній день без уточнення часу передавай в start_time='YYYY-MM-DD 00:00:00 та end_time='YYYY-MM-DD 23:59:59'. "
prompt2 += "При запиті на відміну не уточнюй ім'я та телефон. "
prompt2 += "При вдалій (або невдалій) операції запису (або відміни запису) завжди давай звіт користувачу в чат що зроблено (або не зроблено). "

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
    },
    {
        "type": "function",
        "function": {
            "name": "read_google_sheet_as_dict",
            "description": "Функція що повертає повертає інформацію, щодо наявного переліку послуг та їх вартості.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sheet_name": {
                        "type": "string",
                        "description": f"Назва сторінки Google-документу",
                    },
                    "telegram_id": {
                        "type": "string",
                        "description": f"telegram_id клієнта",
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

    if telegram_id not in messages_buffer:
        messages_buffer[telegram_id] = []

    messages_buffer[telegram_id].append({
        "role": "user",
        "content": text
    })

    base_system_prompt = {
        "role": "system",
        "content": f"{prompt1}\n"
                   f"{prompt2}.\n"
                   f"Поточна дата/час: {now}."
    }

    # Первый запрос
    response = client.chat.completions.create(
        messages=[base_system_prompt] + messages_buffer[telegram_id],
        model=LLM_ID,
        tools=functions
    )

    ai_message = response.choices[0].message

    if ai_message.content:
        messages_buffer[telegram_id].append({
            "role": "assistant",
            "content": ai_message.content
        })
        return ai_message.content

    if ai_message.tool_calls:
        tool_responses = []

        for tool_call in ai_message.tool_calls:
            try:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                tool_args["telegram_id"] = telegram_id

                result = functions_register[tool_name](**tool_args)

                tool_responses.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })

            except Exception as e:
                tool_responses.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": f"Помилка виконання функції {tool_name}: {str(e)}"
                })

        # ВАЖНО: добавляем assistant-сообщение в правильной структуре
        messages_buffer[telegram_id].append({
            "role": "assistant",
            "content": "",
            "tool_calls": [tc.model_dump() for tc in ai_message.tool_calls]
        })

        messages_buffer[telegram_id].extend(tool_responses)

        print("🚨 DEBUG: messages going to second OpenAI call:")
        pprint.pprint(messages_buffer[telegram_id])

        final_response = client.chat.completions.create(
            messages=[base_system_prompt] + messages_buffer[telegram_id],
            model=LLM_ID,
            tools=functions
        )

        final_message = final_response.choices[0].message
        messages_buffer[telegram_id].append({
            "role": "assistant",
            "content": final_message.content
        })

        return final_message.content or "Операцію виконано."

    return "Не вдалося отримати відповідь від помічника."


def audio_assistant(message: Message, audio_text: str, client: OpenAI) -> str:
    if not audio_text or not audio_text.strip():
        return "Не вдалося розпізнати голос. Будь ласка, повторіть ще раз."
    telegram_id = message.from_user.id
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


    if telegram_id not in messages_buffer:
        messages_buffer[telegram_id] = []

    messages_buffer[telegram_id].append({
        "role": "user",
        "content": audio_text.strip()
    })

    base_system_prompt = {
        "role": "system",
        "content": f"{prompt1}\n"
                   f"{prompt2}.\n"
                   f"Поточна дата/час: {now}."
    }

    # очищаем историю от пустых сообщений
    cleaned_messages = [
        m for m in messages_buffer[telegram_id]
        if isinstance(m.get("content"), str) and m["content"].strip() != "" or m.get("tool_calls")
    ]

    # print("📤 Отправляем messages:")
    # pprint.pprint([base_system_prompt] + cleaned_messages)

    response = client.chat.completions.create(
        messages=[base_system_prompt] + cleaned_messages,
        model=LLM_ID,
        tools=functions
    )

    ai_message = response.choices[0].message

    if ai_message.content:
        messages_buffer[telegram_id].append({
            "role": "assistant",
            "content": ai_message.content or ""  # всегда добавляем строку, даже если пустую
        })
        return ai_message.content

    if ai_message.tool_calls:
        tool_responses = []

        for tool_call in ai_message.tool_calls:
            try:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                tool_args["telegram_id"] = telegram_id

                result = functions_register[tool_name](**tool_args)

                tool_responses.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })

            except Exception as e:
                tool_responses.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": f"Помилка при виконанні функції {tool_name}: {str(e)}"
                })

        # ВАЖНО: правильный assistant с tool_calls
        messages_buffer[telegram_id].append({
            "role": "assistant",
            "content": "",
            "tool_calls": [tc.model_dump() for tc in ai_message.tool_calls]
        })

        messages_buffer[telegram_id].extend(tool_responses)

        cleaned_messages = [
            m for m in messages_buffer[telegram_id]
            if isinstance(m.get("content"), str) and m["content"].strip() != "" or m.get("tool_calls")
        ]

        print("🚨 DEBUG: messages going to second OpenAI call:")
        pprint.pprint([base_system_prompt] + cleaned_messages)

        final_response = client.chat.completions.create(
            messages=[base_system_prompt] + cleaned_messages,
            model=LLM_ID,
            tools=functions
        )

        final_message = final_response.choices[0].message
        messages_buffer[telegram_id].append({
            "role": "assistant",
            "content": final_message.content
        })

        return final_message.content or "Операцію виконано."

    return "Не вдалося отримати відповідь від помічника."