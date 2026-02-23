import pymysql

class Config:
    SECRET_KEY = "Kblinb@123"

    DB_HOST = "127.0.0.1"
    DB_USER = "root"
    DB_PASSWORD = "Kblinb@123"
    DB_NAME = "cms"


def get_connection():
    return pymysql.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        cursorclass=pymysql.cursors.DictCursor
    )
