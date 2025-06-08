from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
import os

class GoogleCalendarClient:
    def __init__(self):
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            "creds.json",
            ["https://www.googleapis.com/auth/calendar"]
        )
        self.service = build("calendar", "v3", credentials=creds)
        self.calendar_id = os.getenv("CALENDAR_ID")

    def book_event(self, user_id, service, start_time):
        event = {
            'summary': f"{user_id}: {service}",
            'start': {'dateTime': start_time, 'timeZone': 'Europe/Kyiv'},
            'end': {'dateTime': start_time, 'timeZone': 'Europe/Kyiv'}
        }
        event = self.service.events().insert(calendarId=self.calendar_id, body=event).execute()
        return event

    def list_for_user(self, user_id):
        now = datetime.utcnow().isoformat() + 'Z'
        events = self.service.events().list(calendarId=self.calendar_id, timeMin=now).execute().get('items', [])
        return [e for e in events if str(user_id) in e.get('summary', '')]
