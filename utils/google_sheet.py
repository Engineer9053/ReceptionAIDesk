import json
import gspread
from typing import List, Dict
from configs import GOOGLE_CREDENTIALS_JSON, SHEET_ID
from oauth2client.service_account import ServiceAccountCredentials
from typing import List, Dict, Optional


scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
# Читаем путь к JSON-файлу или сам JSON из переменной
if GOOGLE_CREDENTIALS_JSON.endswith('.json'):
    creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDENTIALS_JSON, scope)
else:
    creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(GOOGLE_CREDENTIALS_JSON), scope)

client = gspread.authorize(creds)


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

