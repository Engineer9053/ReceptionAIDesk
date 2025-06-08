import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os

class GoogleSheetsClient:
    def __init__(self):
        scope = ["https://spreadsheets.google.com/feeds",
                 "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
        client = gspread.authorize(creds)
        self.sheet = client.open_by_key(os.getenv("SHEETS_ID")).sheet1

    def list_services(self):
        return self.sheet.col_values(1)[1:]  # первая колонка, без заголовка