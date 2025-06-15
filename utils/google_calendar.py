import datetime
import json
import os
from configs import CALENDAR_ID, GOOGLE_CREDENTIALS_JSON
from google.oauth2 import service_account
from googleapiclient.discovery import build
from zoneinfo import ZoneInfo



credentials = service_account.Credentials.from_service_account_info(
    json.loads(GOOGLE_CREDENTIALS_JSON),
    scopes=["https://www.googleapis.com/auth/calendar"]
)

calendar = build("calendar", "v3", credentials=credentials)

def create_event(summary: str, description: str, start_time: str, duration_minutes: int):
    user_timezone = "Europe/Kyiv"
    local_tz = ZoneInfo(user_timezone)
    start_local = datetime.datetime.fromisoformat(start_time).replace(tzinfo=local_tz)
    end_local = start_local + datetime.timedelta(minutes=duration_minutes)

    start_utc = start_local.astimezone(datetime.timezone.utc)
    end_utc = end_local.astimezone(datetime.timezone.utc)

    event = {
        'summary': summary,
        'description': description,
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

    event_result = calendar.events().insert(
        calendarId=CALENDAR_ID,
        #conferenceDataVersion=1, # генерация ссылки на гугл-мит доступна только для корпоративного аккаунта, как и возможность приглашать гостей не евент
        body=event
    ).execute()

    return {
        'event_link': event_result.get('htmlLink'),
        'meet_link': event_result.get('conferenceData', {}).get('entryPoints', [{}])[0].get('uri')
    }


def cancel_event(event_id: str) -> bool:
    """
    Отменяет событие в календаре по его идентификатору.
    :param event_id: Идентификатор события в календаре Google
    :return: True, если успешно удалено, False — в случае ошибки
    """
    try:
        calendar.events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()
        print(f"Событие {event_id} успешно удалено.")
        return True
    except Exception as e:
        print(f"Ошибка при удалении события: {e}")
        return False





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