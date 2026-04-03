from DateBase.connection import S3Client
import asyncio
from conf import SETTINGS


def upload_file_to_s3(file_path: str):
    s3 = S3Client()
    with open(SETTINGS['WORK_DIR'] + file_path, 'rb') as f:
        file = f.read()

    asyncio.run(
        s3.upload_bfile(file=file, name=f'first_frame/{file_path}')
    )


