import threading
import os
import time

from DateBase.connection import DbRequest
from DateBase.utils import upload_file_to_s3
from Transcription.utils import load_model, transcription_worker, transcription, save_video, mp4_to_wav, get_length, download_first_frame
from llm.utils import make_ocr, make_annotation, make_embedding

from conf import log, empty_annotation

def main():
    while True:
        psql = DbRequest()
        state = psql.update_task_status()
        if state == 'running':
            reel = psql.get_reel_for_processing()
            log(f"Reel {reel} 🎯")
            reel_state = psql.get_state_reel(reel)
            log(f"Начнем с {reel_state} 🚗")

            if reel_state == 'transcription':
                status_save = save_video(reel)
                if status_save:
                    log("скачено ✅")

                    wav_state = mp4_to_wav(reel)
                    if wav_state:
                        log("mp4 -> wav ✅")

                        duration = get_length(reel)
                        log(f"Длина: {duration} c.")

                        text = transcription('ru')
                        psql.save_reel_text(reel, text)
                        psql.save_reel_ts_vector(reel)
                        psql.update_reel_duration(reel, duration)

                        download_first_frame(reel)
                        log("скачивание кадра первой секунды 🖼️")
                        upload_file_to_s3(reel+'.jpg')
                        log("Кадр загружен ан S3 💿")


                        reel_state = 'frames_data'

            if reel_state == 'transcription':
                psql.save_reel_text(reel, 'error_save')
                psql.save_reel_ocr(reel, {})
                annotation = empty_annotation
                annotation['reel_code'] = reel
                psql.save_reel_annotation(annotation)
                psql.save_embedding([0 for i in range(1536)], reel)


            if reel_state == 'frames_data':
                data = make_ocr(reel)
                log('Получил данные с кадров 👁️👁️')
                psql.save_reel_ocr(reel, data)
                log('Данные о кадрах записаны в бд 🖼️✍️')
                reel_state = 'annotation'

                if os.path.exists(reel + '.mp4'):
                    os.remove(reel + '.mp4')
                if os.path.exists(reel + '.jpg'):
                    os.remove(reel + '.jpg')
                if os.path.exists(reel + '.wav'):
                    os.remove(reel + '.wav')

            if reel_state == 'annotation':
                views, likes, comments, description, trans, first_frame = psql.get_reel_metrics(reel)
                annotation = make_annotation(
                    views=views, likes=likes, comments=comments,
                    description=description, trans=trans, first_frame=first_frame
                )

                annotation['reel_code'] = reel
                annotation['model'] = 'gpt-4o'
                annotation['prompt_version'] = 1
                annotation['schema_version'] = 1
                log('Получил методанные о рилсе тема, хук...💬')
                psql.save_reel_annotation(annotation)
                log('Метаданные записаны в бд 💬✍️')
                reel_state = 'embedding'

            if reel_state == 'embedding':

                with open('llm/embedding', 'r') as f:
                    text = f.read()

                parms = psql.get_annotation(reel)

                for n, par in enumerate(parms):
                    text.replace(f'$%{n}%$', par)

                embedding = make_embedding(text)
                log('Получил EMBEDDING ↗️')
                psql.save_embedding(embedding, reel)
                log('Сохранил EMBEDDING ✍️')

            psql.close()
        else:
            psql.close()
            time.sleep(60 * 60 * 2)


if __name__ == '__main__':
    # Загружаем модель
    load_model()
    # Запускаем рабочий поток
    worker_thread = threading.Thread(target=transcription_worker, daemon=True)
    worker_thread.start()
    main()