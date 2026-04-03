import psycopg2
from contextlib import asynccontextmanager
from aiobotocore.session import get_session
from httpx import AsyncClient

import json

from conf import SETTINGS

from datetime import datetime
from datetime import timezone
utc_tz = timezone.utc

from typing import Literal

class DbRequest:
    def __init__(self):
        self.connection = psycopg2.connect(
            user=SETTINGS["DB_USER"],
            password=SETTINGS["DB_PASSWORD"],
            dbname=SETTINGS["DB_NAME"],
            host=SETTINGS["DB_HOST"],
            port=SETTINGS["DB_PORT"]
        )

        self.connection.autocommit = True
        self.cursor = self.connection.cursor()

    def close(self):
        self.cursor.close()
        self.connection.close()

    def get(self, table: str, columns: list = False, q: dict = None) -> list:
        """Метод получения данных колонки (некоторых или всех) из таблицы"""

        columns = columns if columns is False else ', '.join(columns)

        request = f"select {columns} from {table}"
        if q is not None:
            request += ' where '
            for n, value in enumerate(q):
                if type(q[value]) == str:
                    p_value = f"'{q[value]}'"
                else:
                    p_value = q[value]

                if value[0] == '!':
                    request += f"{value[1:]} != {p_value}"
                else:
                    request += f"{value} = {p_value}"
                if n < len(q) - 1:
                    if len(q) != 1:
                        request += ' AND '

        self.cursor.execute(request)
        return self.cursor.fetchall()

    def get_all_reels(self):
        """Получение всех рилс в бд"""
        reels_id = self.get('reels', columns=['id'])
        print(reels_id)


    def update_task_status(self):
        task_id, state = \
        self.get('parser_history', columns=['id', 'state'], q={'task_type': 'post_processing'})[0]

        # all_reels = self.get('reels', columns=['count(code)'])[0][0]
        q = f"select count(r.code) from reels r left join authors a on r.author_id = a.id where a.language = 'ru'"
        self.cursor.execute(q)
        all_reels = self.cursor.fetchall()[0][0]

        q = (
            f"select count(r.code) from reels r "
            f"left join authors a on r.author_id = a.id "
            f"left join reels_embeddings re on re.reel_code = r.code "
            f"where a.language = 'ru' and exists(select 1 from reels_embeddings where reel_code = r.code) "
        )
        self.cursor.execute(q)
        done_reels = self.cursor.fetchall()[0][0]

        # done_reels = self.get('reels_transcriptions', columns=['count(reel_code)'], q={'!text': 'wait_for_transcription'})[0][0]

        now = datetime.now(utc_tz)

        if state == 'running':
            if all_reels == done_reels:
                state = 'finished'
                q = f"update parser_history set (stop_time, state, reels_added, reels_total) = ('{now}', '{state}', {done_reels}, {all_reels}) where id = {task_id} "
            else:
                q = f'update parser_history set (reels_added, reels_total) = ({done_reels}, {all_reels}) where id = {task_id} '

        else:
            state = 'running'
            q = f"update parser_history set (start_time, state, reels_added, reels_total) = ('{now}', '{state}', {done_reels}, {all_reels}) where id = {task_id} "

        self.cursor.execute(q)
        return state


    def get_reel_for_processing(self):
        q = "SELECT code FROM reels r left join authors a on r.author_id = a.id WHERE not exists(select 1 from reels_embeddings where reel_code = r.code) and a.language = 'ru' limit 1;"
        self.cursor.execute(q)
        return self.cursor.fetchall()[0][0]


    def get_state_reel(self, reel_code: str) -> Literal['transcription', 'frames_data', 'annotation', 'embedding']:

        transcription = self.get('reels_transcriptions', columns=['text'], q={'reel_code': reel_code})

        if len(transcription) == 0 or transcription[0][0] == 'wait_for_transcription':
            return 'transcription'

        frames_data = self.get('reels_frames_data', columns=['data'], q={'reel_code': reel_code})
        if len(frames_data) == 0 or frames_data[0][0] == {}:
            return 'frames_data'

        annotation = self.get('reels_post_metrics', columns=['reel_code'], q={'reel_code': reel_code})
        if len(annotation) == 0:
            return 'annotation'

        return 'embedding'

    def get_reel_metrics(self, reel_code: str):
        q = (
            f"select r.views, r.likes, r.comments, r.description, rt.text, rf.data "
            f"from reels r left join reels_transcriptions rt on rt.reel_code = r.code "
            f"left join reels_frames_data rf on rf.reel_code = r.code "
            f"where r.code = '{reel_code}'"
        )

        self.cursor.execute(q)
        return self.cursor.fetchall()[0]

    def save_reel_text(self, reel_code: str, text: str):
        text = text.replace('$', '💲')
        q = f"update reels_transcriptions set text = $${text}$$ where reel_code = '{reel_code}' "
        self.cursor.execute(q)

    def update_reel_duration(self, reel_code: str, duration: int):
        q = f"update reels set duration = {duration} where code = '{reel_code}'"
        self.cursor.execute(q)

    def save_reel_ts_vector(self, reel_code: str):
        q = f"select reel_code from reels_ts_vectors where reel_code = '{reel_code}'"
        self.cursor.execute(q)
        ts_id = self.cursor.fetchall()

        if ts_id:
            q = f"update reels_ts_vectors set vector = to_tsvector(COALESCE((select description from reels where code = '{reel_code}'), '') || ' ' || COALESCE((select text from reels_transcriptions where reel_code = '{reel_code}'), '')) where reel_code = '{ts_id[0][0]}' "
        else:
            q = f"INSERT INTO reels_ts_vectors (reel_code, vector) values ('{reel_code}', to_tsvector(COALESCE((select description from reels where code = '{reel_code}'), '') || ' ' || COALESCE((select text from reels_transcriptions where reel_code = '{reel_code}'), '')) )"

        self.cursor.execute(q)

    def save_reel_ocr(self, reel_code: str, data: dict):
        json_data = json.dumps(data, ensure_ascii=False)
        q = """
            INSERT INTO reels_frames_data (reel_code, data)
            VALUES (%s, %s::jsonb)
            ON CONFLICT (reel_code) DO UPDATE
                SET data = EXCLUDED.data
        """
        self.cursor.execute(q, (reel_code, json_data))

    def save_reel_annotation(self, data: dict):
        rwas = ', '.join(list(data))
        values = []
        for par in data:
            if par in ['emotional_triggers', 'virality_mechanics_primary', 'cross_niche_tags']:
                values.append(f"'{json.dumps(data[par])}'")
            else:
                if type(data[par]) == int:
                    values.append(f"{data[par]}")
                else:
                    values.append(f"$${data[par]}$$")

        q = f"INSERT INTO reels_post_metrics ({rwas}) values ( {', '.join(values)})"
        self.cursor.execute(q)


    def save_embedding(self, embedding: list[float], reel_code: str):
        self.cursor.execute(f"INSERT INTO reels_embeddings (reel_code, embedding) VALUES ('{reel_code}', '{embedding}')")

    def get_annotation(self, reel_code: str):
        self.cursor.execute(
            f"select topic, subtopic, niche_primary, niche_secondary, viewer_problem,"
            f" viewer_desire, core_idea, short_summary, rt.text, r.description "
            f"from reels_post_metrics rp left join reels r on rp.reel_code = r.code "
            f"left join reels_transcriptions rt on rt.reel_code = rp.reel_code "
            f"where rp.reel_code = '{reel_code}' "
        )
        return self.cursor.fetchall()


class S3Client:
    def __init__(
            self):

        self.config = {
                "aws_access_key_id": SETTINGS['ACCESS_KEY'],
                "aws_secret_access_key": SETTINGS['SECRET_KEY'],
                "endpoint_url": SETTINGS['S3_ENDPOINT'],
            }

        self.bucket_name = SETTINGS['BUCKET_NAME']
        self.session = get_session()


    @asynccontextmanager
    async def get_client(self):
        async with self.session.create_client("s3", **self.config) as client:
            yield client

    async def upload_bfile(self, file: bytes, name: str):
        async with self.get_client() as client:
            await client.put_object(Bucket=self.bucket_name, Key=name, Body=file)