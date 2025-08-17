import json
import gspread
from datetime import datetime, timedelta, time, timezone
from configs import CALENDAR_ID, GOOGLE_CREDENTIALS_JSON, SHEET_ID
from google.oauth2 import service_account
from googleapiclient.discovery import build
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

def create_event(
    summary: str,
    description: str,
    start_time: str,
    duration_minutes: int,
    telegram_id: int,
    user_timezone: str = "Europe/Kyiv"
) -> dict:
    """
    Создаёт событие в Google Calendar и возвращает полный объект события.
    """

    local_tz = ZoneInfo(user_timezone)
    start_local = datetime.fromisoformat(start_time).replace(tzinfo=local_tz)
    end_local = start_local + timedelta(minutes=duration_minutes)

    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)

    event = {
        'summary': summary,
        'description': description + f" (telegram_id:{telegram_id})",
        'start': {
            'dateTime': start_utc.isoformat(),
            'timeZone': user_timezone,
        },
        'end': {
            'dateTime': end_utc.isoformat(),
            'timeZone': user_timezone,
        },
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
            body=event
        ).execute()

        # 🔥 возвращаем полный объект события (всё, что вернул API Google Calendar)
        return {
            "status": "success",
            "event": event_result
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

def check_free_slots(
    start_time: str,
    duration_minutes: int = 0,
    end_time: str = None,
    user_timezone: str = "Europe/Kyiv",
    telegram_id: int = 0
) -> dict:
    """
    Проверяет свободные слоты в календаре.
    Если duration_minutes > 0 — проверка конкретного слота (возвращает is_free),
    иначе возвращает массив всех свободных интервалов в указанном диапазоне.
    """

    local_tz = ZoneInfo(user_timezone)
    start_local = datetime.fromisoformat(start_time).replace(tzinfo=local_tz)
    end_local = start_local + timedelta(minutes=duration_minutes) if duration_minutes > 0 else datetime.fromisoformat(end_time).replace(tzinfo=local_tz)

    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)

    try:
        events_result = calendar.freebusy().query(
            body={
                "timeMin": start_utc.isoformat().replace('+00:00', 'Z'),
                "timeMax": end_utc.isoformat().replace('+00:00', 'Z'),
                "items": [{"id": CALENDAR_ID}]
            }
        ).execute()

        busy_periods = events_result['calendars'][CALENDAR_ID].get('busy', [])

        if duration_minutes > 0:
            # Проверка конкретного слота
            is_free = len(busy_periods) == 0
            return {"status": "success", "is_free": is_free}

        # Вычисление всех свободных интервалов
        busy_periods_dt = [
            (
                datetime.fromisoformat(p['start'].replace('Z', '+00:00')).astimezone(local_tz),
                datetime.fromisoformat(p['end'].replace('Z', '+00:00')).astimezone(local_tz)
            )
            for p in busy_periods
        ]
        busy_periods_dt.sort()

        WORK_START = time(8, 0)
        WORK_END = time(20, 0)

        current = start_local
        free_slots = []

        while current < end_local:
            # Выходные
            if current.weekday() == 6:  # воскресенье
                current = datetime.combine((current + timedelta(days=1)).date(), WORK_START, tzinfo=local_tz)
                continue
            if current.weekday() == 5:  # суббота
                WORK_START = time(10, 0)
                WORK_END = time(18, 0)

            day_start = datetime.combine(current.date(), WORK_START, tzinfo=local_tz)
            day_end = datetime.combine(current.date(), WORK_END, tzinfo=local_tz)
            pointer = day_start

            for busy_start, busy_end in busy_periods_dt:
                if busy_end <= pointer or busy_start >= day_end:
                    continue
                if busy_start > pointer:
                    slot_start = pointer
                    slot_end = min(busy_start, day_end)
                    if slot_start < slot_end:
                        free_slots.append({"start": slot_start.isoformat(), "end": slot_end.isoformat()})
                pointer = max(pointer, busy_end)

            if pointer < day_end:
                free_slots.append({"start": pointer.isoformat(), "end": day_end.isoformat()})

            current = datetime.combine((current + timedelta(days=1)).date(), WORK_START, tzinfo=local_tz)

        return {"status": "success", "free_slots": free_slots}

    except Exception as e:
        return {"status": "error", "error": str(e)}


def cancel_event(
    start_time_local: str,
    end_time_local: str,
    telegram_id: int,
    user_timezone: str = "Europe/Kyiv",
    query: str = None
) -> dict:
    """
    Ищет и удаляет события в календаре Google для указанного пользователя и диапазона времени.
    Возвращает список полных данных удалённых событий (чтобы при необходимости их можно было восстановить).
    """

    tz = ZoneInfo(user_timezone)
    start_dt = datetime.fromisoformat(start_time_local).replace(tzinfo=tz).astimezone(timezone.utc)
    end_dt = datetime.fromisoformat(end_time_local).replace(tzinfo=tz).astimezone(timezone.utc)

    start_time_iso = start_dt.isoformat().replace("+00:00", "Z")
    end_time_iso = end_dt.isoformat().replace("+00:00", "Z")

    try:
        events_result = calendar.events().list(
            calendarId=CALENDAR_ID,
            timeMin=start_time_iso,
            timeMax=end_time_iso,
            timeZone=user_timezone,
            q=str(telegram_id),   # фильтруем по telegram_id
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        list_events = events_result.get("items", [])

        if not list_events:
            return {
                "status": "not_found",
                "deleted": [],
                "message": "No events found for given parameters"
            }

        deleted = []
        errors = []

        for event_row in list_events:
            event_id = event_row.get("id")
            try:
                # ⚠️ сохраним полное событие ДО удаления
                deleted.append(event_row)

                # удаляем событие из Google Calendar
                calendar.events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()

            except Exception as e:
                errors.append({
                    "event_id": event_id,
                    "error": str(e)
                })

        return {
            "status": "success" if not errors else "partial_success",
            "deleted": deleted,   # 🔥 массив ПОЛНЫХ событий (все поля summary, description, start, end и т.д.)
            "errors": errors
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def find_events_by_time(
    start_time_local: str,
    end_time_local: str,
    telegram_id: int,
    user_timezone: str = "Europe/Kyiv",
    query: str = None
) -> list[dict]:
    """
    Ищет события в календаре с учётом часового пояса пользователя.
    :param start_time_local: Локальное время начала (ISO строка, например, "2025-06-12T00:00:00")
    :param end_time_local: Локальное время конца
    :param telegram_id: ID пользователя для поиска в описании
    :param user_timezone: Таймзона пользователя (например, "Europe/Kyiv")
    :param query: Дополнительный текст для поиска в summary/description
    :return: Список найденных событий (полные объекты из Google Calendar API)
    """

    tz = ZoneInfo(user_timezone)
    start_dt = datetime.fromisoformat(start_time_local).replace(tzinfo=tz).astimezone(timezone.utc)
    end_dt = datetime.fromisoformat(end_time_local).replace(tzinfo=tz).astimezone(timezone.utc)

    start_time_iso = start_dt.isoformat().replace("+00:00", "Z")
    end_time_iso = end_dt.isoformat().replace("+00:00", "Z")

    try:
        events_result = calendar.events().list(
            calendarId=CALENDAR_ID,
            timeMin=start_time_iso,
            timeMax=end_time_iso,
            timeZone=user_timezone,
            q=f"{telegram_id} {query}" if query else str(telegram_id),
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        list_events = events_result.get("items", [])
        return list_events

    except Exception as e:
        print(f"Ошибка при поиске событий: {e}")
        return []


def read_google_sheet_as_dict(sheet_name: str = "Price", telegram_id: int = 0) -> str:

    # Открываем таблицу
    sheet = client.open_by_key(SHEET_ID)
    print("---------------------------------------------------------------------------- call read_google_sheet_as_dict")
    # Выбираем первый лист (или по имени)
    worksheet = sheet.worksheet(sheet_name) if sheet_name else sheet.get_worksheet(0)

    # Получаем все строки как список словарей: [{col1: val1, col2: val2, ...}, ...]
    records = worksheet.get_all_records()

    output = "\n".join(
        f"{i + 1}. {service['Service']}. Опис послуги: {service['Description of service']}. Вартість послуги: {service['Price,$']}$"
        for i, service in enumerate(records)
    )

    return output


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
    "read_google_sheet_as_dict": read_google_sheet_as_dict,
    "check_free_slots": check_free_slots,
    "create_event": create_event,
    "cancel_event": cancel_event,
    "find_events_by_time": find_events_by_time
}