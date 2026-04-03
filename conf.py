from dotenv import load_dotenv
import os
from datetime import datetime


def get_settings() -> dict:
    load_dotenv()
    parameters = [
        'DB_USER', 'DB_PASSWORD', 'DB_NAME', 'DB_HOST', 'DB_PORT',
        'S3_ENDPOINT', 'ACCESS_KEY', 'SECRET_KEY', 'BUCKET_NAME', 'S3_BASE_URL',
        'OPEN_AI_TOKEN',
        'WORK_DIR',
        'EmbeddingToken', 'EMBEDDING_URL'
    ]

    settings = {}
    for parameter in parameters:
        settings[parameter] = os.getenv(parameter)
    return settings

def log(*kwargs):
    out_file = 'logs.txt'
    out = ''
    for kwarg in kwargs:
        out += f' {kwarg}'

    if os.path.exists(out_file):
        mode = 'a'
    else:
        mode = 'w'

    with open(out_file, mode=mode, encoding='utf-8') as f:
        now = datetime.now()
        date_str = f"[ {now.day}.{now.month} | {now.hour}:{now.minute} ] "
        f.write(date_str + out + "\n")

    print(out)

SETTINGS = get_settings()
