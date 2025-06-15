from io import BytesIO
from typing import Any

import datetime
import json
import gspread
import os
from configs import CALENDAR_ID, GOOGLE_CREDENTIALS_JSON, SHEET_ID
from google.oauth2 import service_account
from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
from zoneinfo import ZoneInfo
from typing import List, Dict, Optional


scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive",
         "https://www.googleapis.com/auth/calendar"]

credentials = service_account.Credentials.from_service_account_info(
    json.loads(GOOGLE_CREDENTIALS_JSON),
    scopes=scope
)
client = gspread.authorize(credentials)

calendar = build("calendar", "v3", credentials=credentials)

def create_event(summary: str, description: str, start_time: str, duration_minutes: int, telegram_id: int) -> str:
    user_timezone = "Europe/Kyiv"
    local_tz = ZoneInfo(user_timezone)
    start_local = datetime.datetime.fromisoformat(start_time).replace(tzinfo=local_tz)
    end_local = start_local + datetime.timedelta(minutes=duration_minutes)

    start_utc = start_local.astimezone(datetime.timezone.utc)
    end_utc = end_local.astimezone(datetime.timezone.utc)

    event = {
        'summary': summary,
        'description': description + "(telegram_id:" + str(telegram_id) + ")",
        'start': {
            'dateTime': start_utc.isoformat(),
            'timeZone': user_timezone,
        },
        'end': {
            'dateTime': end_utc.isoformat(),
            'timeZone': user_timezone,
        },
        #'conferenceData': { # генерация ссылки на гугл-мит доступна только для корпоративного аккаунта, как и возможность приглашать гостей не евент
        #    'createRequest': {
        #        'requestId': f'meeting-{start_utc.timestamp()}',
        #        'conferenceSolutionKey': {'type': 'hangoutsMeet'},
        #    }
        #},
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'popup', 'minutes': 30},
                {'method': 'email', 'minutes': 30}
            ]
        }
    }

    try:
        event_result = calendar.events().insert(
            calendarId=CALENDAR_ID,
            #conferenceDataVersion=1, # генерация ссылки на гугл-мит доступна только для корпоративного аккаунта, как и возможность приглашать гостей не евент
            body=event
        ).execute()

        response = f"Виконано!\nСтворено запис на сеанс з '{start_local}' по {end_local} ({user_timezone}). {summary}"

    except Exception:

        response = "Помилка!\nНа жаль запис не вдалося створити. Спробуй ще раз."

    # return {
    #         'event_link': event_result.get('htmlLink'),
    #         'meet_link': event_result.get('conferenceData', {}).get('entryPoints', [{}])[0].get('uri')
    #     }

    return response


def cancel_event(start_time_local: str, end_time_local: str, telegram_id: int, user_timezone: str = "Europe/Kyiv", query: str = None):
        """
        Ищет события в календаре с учётом часового пояса пользователя.
        :param start_time_local: Локальное время начала (ISO строка, например, "2025-06-12T00:00:00")
        :param end_time_local: Локальное время конца
        :param user_timezone: Таймзона пользователя, например "Europe/Kyiv"
        :param query: Текст для поиска в summary/description
        :return: Список найденных событий
        """
        tz = ZoneInfo(user_timezone)
        start_dt = datetime.datetime.fromisoformat(start_time_local).replace(tzinfo=tz).astimezone(
            datetime.timezone.utc)
        end_dt = datetime.datetime.fromisoformat(end_time_local).replace(tzinfo=tz).astimezone(datetime.timezone.utc)

        start_time_iso = start_dt.isoformat().replace("+00:00", "Z")
        end_time_iso = end_dt.isoformat().replace("+00:00", "Z")

        response = ""

        events_result = calendar.events().list(
            calendarId=CALENDAR_ID,
            timeMin=start_time_iso,
            timeMax=end_time_iso,
            timeZone=user_timezone,
            q=str(telegram_id),
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        list_events = events_result.get("items", [])
        for event_row in list_events:
            try:
                event_id = event_row['id']
            except Exception as e:
                print(f"Событие не найдено: {e}")
                return "Событие не найдено"
            """
            Отменяет событие в календаре по его идентификатору.
            :param event_id: Идентификатор события в календаре Google
            :return: True, если успешно удалено, False — в случае ошибки
            """
            try:
                calendar.events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()
                print(f"Событие {event_id} успешно удалено.")
                response += f"Событие ({event_row['start']['dateTime']}) успешно удалено. "
            except Exception as e:
                print(f"Ошибка при удалении события: {e}")
                response += f"Ошибка при удалении события ({event_row['start']['dateTime']})"

        return response

def find_events_by_time(
            start_time_local: str,
            end_time_local: str,
            user_timezone: str = "Europe/Kyiv",
            query: str = None
    ):
        """
        Ищет события в календаре с учётом часового пояса пользователя.
        :param start_time_local: Локальное время начала (ISO строка, например, "2025-06-12T00:00:00")
        :param end_time_local: Локальное время конца
        :param user_timezone: Таймзона пользователя, например "Europe/Kyiv"
        :param query: Текст для поиска в summary/description
        :return: Список найденных событий
        """
        tz = ZoneInfo(user_timezone)
        start_dt = datetime.datetime.fromisoformat(start_time_local).replace(tzinfo=tz).astimezone(
            datetime.timezone.utc)
        end_dt = datetime.datetime.fromisoformat(end_time_local).replace(tzinfo=tz).astimezone(datetime.timezone.utc)

        start_time_iso = start_dt.isoformat().replace("+00:00", "Z")
        end_time_iso = end_dt.isoformat().replace("+00:00", "Z")

        events_result = calendar.events().list(
            calendarId=CALENDAR_ID,
            timeMin=start_time_iso,
            timeMax=end_time_iso,
            timeZone=user_timezone,
            q=query,
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        return events_result.get("items", [])


def check_free_slots(start_time: str, duration_minutes: int):
    user_timezone = "Europe/Kyiv"
    local_tz = ZoneInfo(user_timezone)
    start_local = datetime.datetime.fromisoformat(start_time).replace(tzinfo=local_tz)
    end_local = start_local + datetime.timedelta(minutes=duration_minutes)

    start_utc = start_local.astimezone(datetime.timezone.utc)
    end_utc = end_local.astimezone(datetime.timezone.utc)

    events_result = calendar.freebusy().query(
        body={
            "timeMin": start_utc.isoformat().replace('+00:00', 'Z'),
            "timeMax": end_utc.isoformat().replace('+00:00', 'Z'),
            "items": [{"id": CALENDAR_ID}]
        }
    ).execute()

    busy_times = events_result['calendars'][CALENDAR_ID].get('busy', [])
    return len(busy_times) == 0  # Свободен, если нет пересечений


def read_google_sheet_as_dict(sheet_name: str = None) -> List[Dict[str, str]]:

    # Открываем таблицу
    sheet = client.open_by_key(SHEET_ID)

    # Выбираем первый лист (или по имени)
    worksheet = sheet.worksheet(sheet_name) if sheet_name else sheet.get_worksheet(0)

    # Получаем все строки как список словарей: [{col1: val1, col2: val2, ...}, ...]
    records = worksheet.get_all_records()

    return records


def upload_dicts_to_sheet(data: List[Dict], sheet_name: str = None):
    if not data:
        print("Пустой список — нечего загружать.")
        return

    # Открываем таблицу
    sheet = client.open_by_key(SHEET_ID)

    # Пытаемся получить лист
    try:
        worksheet = sheet.worksheet(sheet_name) if sheet_name else sheet.get_worksheet(0)
    except gspread.exceptions.WorksheetNotFound:
        print(f"Лист '{sheet_name}' не найден. Создаю новый...")
        worksheet = sheet.add_worksheet(title=sheet_name, rows="100", cols="20")

    # Подготовка данных
    headers = list(data[0].keys())
    values = [headers] + [[str(row.get(col, "")) for col in headers] for row in data]

    worksheet.clear()
    worksheet.update("A1", values)

    print(f"Загрузка завершена в лист '{worksheet.title}'")



def upsert_services(
    data: List[Dict],
    position: str,
    price: Optional[float] = None,
    description: Optional[str] = None
) -> List[Dict]:
    # Поиск по позиции (услуге)
    for i, row in enumerate(data):
        if row["Service"] == position:
            if price <= 0:
                del data[i]
                return data
            if price is not None:
                row["Price,$"] = price
            if description is not None:
                row["Description of service"] = description
            return data  # Обновили и вернули обновлённый список

    # Если не нашли — добавляем новую услугу
    if price > 0:
        new_row = {"Service": position}
        new_row["Price,$"] = price
        new_row["Description of service"] = description if description is not None else ""
        data.append(new_row)
    return data  # Вернули список с добавленной услугой


functions_register = {
    # "read_google_sheet_as_dict": read_google_sheet_as_dict,
    # "check_free_slots": check_free_slots,
    # "find_events_by_time": find_events_by_time,
    "create_event": create_event,
    "cancel_event": cancel_event
}