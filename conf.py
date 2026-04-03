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

empty_annotation = {
  "topic": "",
  "subtopic": "",
  "niche_primary": "",
  "niche_secondary": "",
  "content_type": "",
  "delivery_format": "",
  "content_structure": "",
  "narrative_device": "",
  "hook_text": "",
  "hook_type": "",
  "viewer_problem": "",
  "viewer_desire": "",
  "emotional_triggers": [],
  "virality_mechanics_primary": [],
  "proof_type": "",
  "cta_type": "",
  "core_idea": "",
  "short_summary": "",
  "production_complexity": "",
  "repeatability_for_expert": "",
  "suitable_for_small_accounts": "",
  "requires_domain_expertise": "",
  "requires_editing_skill": "",
  "can_be_recreated_with_phone": "",
  "content_goal_primary": "",
  "content_goal_secondary": "",
  "adaptation_potential": "",
  "cross_niche_tags": [],
  "signal_source_primary": "",
  "content_understanding_confidence": 0.0,
  "save_ability": "",
  "share_ability": "",
  "comment_ability": "",
  "model": "gpt-4o",
  "prompt_version": 1,
  "schema_version": 1
}