import json

from openai import OpenAI

from config import MODELOS
from prompts_es import PROMPT_FEED, PROMPT_VALIDAR

cliente = OpenAI()


def extraer_datos_feed(fragmento_xml: str) -> dict:
    r = cliente.chat.completions.create(
        model=MODELOS["ligero"],
        temperature=0,
        messages=[
            {"role": "system", "content": PROMPT_FEED},
            {"role": "user", "content": fragmento_xml},
        ],
    )
    return json.loads(r.choices[0].message.content)


def validar_ficha(ficha: dict) -> bool:
    r = cliente.chat.completions.create(
        model=MODELOS["ligero"],
        temperature=0,
        messages=[
            {"role": "system", "content": PROMPT_VALIDAR},
            {"role": "user", "content": json.dumps(ficha, ensure_ascii=False)},
        ],
    )
    return r.choices[0].message.content.strip().upper().startswith("OK")
