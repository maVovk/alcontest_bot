import gspread
from oauth2client.service_account import ServiceAccountCredentials
import csv


def load_to_sheets(table_name = 'Результаты_с_учетом_баллов', csv_data = "table.csv"):
    # Подключение к Google Таблице
    scope = ['https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive']

    creds = ServiceAccountCredentials.from_json_keyfile_name('certificate.json', scope)
    client = gspread.authorize(creds)

    # Открытие CSV файла
    with open(csv_data, 'r') as file:
        csv_data = csv.reader(file)
        data = list(csv_data)

    # Выбор Google Таблицы для загрузки данных
    sheet = client.open(table_name).sheet1

    # Очистка таблицы перед загрузкой новых данных
    sheet.clear()

    # Загрузка данных из CSV файла в Google Таблицу
    sheet.update(range_name='A1', values=data)

