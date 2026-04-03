import httpx
from openai import OpenAI
from conf import SETTINGS, log
import json
import requests


def make_ocr(reel_code):
    http_client = httpx.Client(proxy='http://8yqqpm:5UVBUx@68.209.61.181:8000', timeout=100000)
    client = OpenAI(api_key=SETTINGS['OPEN_AI_TOKEN'], http_client=http_client)

    # Пути к вашим изображениям
    cover = f"{SETTINGS['S3_BASE_URL']}/poster/{reel_code}.jpg"
    frame = f"{SETTINGS['S3_BASE_URL']}/first_frame/{reel_code}.jpg"

    ocr_prot = ''
    with open(SETTINGS['WORK_DIR'] + 'llm/ocr_promt', 'r') as f:
        ocr_prot = f.read()

    # Отправляем запрос с двумя изображениями
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": ocr_prot},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": cover
                        }
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": frame
                        }
                    }
                ]
            }
        ],
        response_format={"type": "json_object"},
        max_tokens=500
    )

    try:
        json_response = json.loads(response.choices[0].message.content)
        return json_response
    except json.JSONDecodeError as e:
        log("Ошибка парсинга JSON:", e)
        return {}


def make_annotation(**kwargs):

    with open(SETTINGS['WORK_DIR'] + 'llm/anno_promt', 'r') as f:
        anno_prot = f.read()

    anno_prot += 'Данные рилс:\n\n'
    for name in kwargs:
        anno_prot += f' {name}: {str(kwargs[name])}\n'


    http_client = httpx.Client(proxy='http://8yqqpm:5UVBUx@68.209.61.181:8000')
    client = OpenAI(api_key=SETTINGS['OPEN_AI_TOKEN'], http_client=http_client)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "user",
             "content": [
                {"type": "text", "text": anno_prot},
             ]
            }],
        response_format={"type": "json_object"}
    )
    try:
        json_response = json.loads(response.choices[0].message.content)
        return json_response
    except json.JSONDecodeError as e:
        log("Ошибка парсинга JSON:", e)
        return {}


def make_embedding(text: str):
    result = requests.post(
        url=SETTINGS['EMBEDDING_URL'],
        headers={'Content-Type': 'application/json'},
        json={
            'prompt': text,
            'token': SETTINGS['EmbeddingToken'],
            'request_id': 'req-001'
        }
    )

    data = result.json()
    if data['status'] == 'success':
        return data['response']
    else:
        return []