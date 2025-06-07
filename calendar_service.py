from google.oauth2 import service_account
from googleapiclient.discovery import build
from config import GOOGLE_CREDENTIALS_JSON, CALENDAR_ID
import json
import datetime

credentials = service_account.Credentials.from_service_account_info(
    json.loads(GOOGLE_CREDENTIALS_JSON),
    scopes=["https://www.googleapis.com/auth/calendar"]
)

calendar = build("calendar", "v3", credentials=credentials)

def check_free_slots(start_time: str, duration_minutes: int):
    start_dt = datetime.datetime.fromisoformat(start_time)
    end_dt = start_dt + datetime.timedelta(minutes=duration_minutes)

    events_result = calendar.freebusy().query(
        body={
            "timeMin": start_dt.isoformat() + 'Z',
            "timeMax": end_dt.isoformat() + 'Z',
            "items": [{"id": CALENDAR_ID}]
        }
    ).execute()

    busy_times = events_result['calendars'][CALENDAR_ID].get('busy', [])
    return len(busy_times) == 0  # Свободен, если нет пересечений

def create_event(summary: str, description: str, start_time: str, duration_minutes: int, attendees: list):
    start_dt = datetime.datetime.fromisoformat(start_time)
    end_dt = start_dt + datetime.timedelta(minutes=duration_minutes)

    event = {
        'summary': summary,
        'description': description,
        'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'UTC'},
        'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'UTC'},
        'attendees': [{'email': email} for email in attendees],
    }
    event_result = calendar.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    return event_result.get("htmlLink")