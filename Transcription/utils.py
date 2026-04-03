import threading
import queue

import subprocess
import requests
import os
from DateBase.connection import S3Client

import asyncio
from conf import log

import whisper

# Глобальные переменные для модели
madal = None
# Глобальная очередь для запросов
request_queue = queue.Queue()
# Словарь для хранения результатов (ключ — request_id)
results = {}
# Блокировка для безопасного доступа к results
results_lock = threading.Lock()


def get_length(reel_uri: str):
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                             "format=duration", "-of",
                             "default=noprint_wrappers=1:nokey=1", f"{reel_uri}.wav"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)

    time = float(result.stdout)

    return round(time)


def mp4_to_wav(reel_uri: str):
    command = f"ffmpeg -i {reel_uri}.mp4 -ab 160k -ac 2 -ar 44100 -vn {reel_uri}.wav"
    subprocess.call(command, shell=True)
    if os.path.exists(f"{reel_uri}.wav"):
        return True
    else:
        return False


def download_first_frame(reel_code: str):
    """
    Извлекает первый кадр видео и сохраняет как изображение.
    """

    video_path = f'{reel_code}.mp4'
    output_path = f'{reel_code}.jpg'

    cmd = [
        'ffmpeg',
        '-ss', '00:00:00',  # Начало — 0 секунд
        '-i', video_path,      # Входной файл
        '-ss', '1',
        '-vframes', '1',     # Только 1 кадр
        '-q:v', '2',        # Качество JPEG (1–31, меньше — лучше)
        '-f', 'image2',     # Формат вывода — одиночное изображение
        output_path         # Путь сохранения
    ]

    subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        text=True
    )


def save_video(reel_uri: str):
    url = f'https://0c9ccab2-b6d2-4250-84bc-70c30e9a0f0c.selstorage.ru/video/{reel_uri}.mp4'
    response = requests.get(url, stream=True)
    # Проверить, был ли запрос успешным
    if response.status_code == 200:
        # Открыть локальный файл в режиме бинарной записи
        with open(f'{reel_uri}.mp4', 'wb') as file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    file.write(chunk)
        return True
    else:
        return False


def upload_first_frame(reel_code: str):
    s3 = S3Client()
    with open(f'{reel_code}.jpg', 'rb') as f:
        file = f.read()

    asyncio.run(
        s3.upload_bfile(file=file, name=f'first_frame/{reel_code}.jpg')
    )

    log("Кадр загружен ан S3 💿")


def load_model(model_name: str = 'turbo'):
    global madal
    model_v = model_name
    log(f"Загружаю модель whisper({model_v}) 💿")
    madal = whisper.load_model(model_v)
    log("Модель загружена 👌")


def transcription_worker():
    """Поток-обработчик запросов из очереди"""
    while True:
        # Получаем запрос из очереди
        reel_code, event = request_queue.get()
        if reel_code is None:  # Сигнал остановки
            break

        try:
            # Генерация ответа
            result = madal.transcribe(f'{reel_code}.wav')

            text = ""
            if result["text"]:
                text = result["text"]

            if text:
                log('Текст:\n', text[:25], '...')

            # Сохраняем результат с блокировкой
            with results_lock:
                results[reel_code] = {
                    'status': 'completed',
                    'text': text
                }

        except Exception as e:
            with results_lock:
                results[reel_code] = {
                    'status': 'error',
                    'error': str(e)
                }

        # Сигнализируем, что обработка завершена
        event.set()
        request_queue.task_done()


def transcription(reel_code):
    # Создаём событие для синхронизации
    event = threading.Event()

    request_queue.put((reel_code, event))

    # Ждём завершения обработки
    if event.wait():
        # Получаем результат с блокировкой
        with results_lock:
            result = results.get(reel_code, {})
            # Удаляем обработанный запрос из кэша
            print(result)
            if reel_code in results:
                del results[reel_code]

        if result.get('status') == 'completed':
            return {
                'status': 'success',
                'reel_code': reel_code,
                'response': result['text']
            }
        else:
            return {
                'status': 'error',
                'reel_code': reel_code,
                'error': result.get('error', 'Unknown error')
            }

    else:
        return {'status': 'error', 'error': 'time_error'}