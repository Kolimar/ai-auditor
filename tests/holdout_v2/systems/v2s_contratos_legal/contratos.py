import json
from datetime import date

from openai import OpenAI

import prompts_es as P

cliente = OpenAI()

CONFIG = {"barato": "gpt-4o-mini", "potente": "gpt-4o"}


def clasificar_vencimiento(contrato: dict, hoy: date) -> str:
    dias = (date.fromisoformat(contrato["vence"]) - hoy).days
    datos = (
        f"dias_restantes: {dias}\n"
        f"renovacion_automatica: {contrato['renovacion_automatica']}\n"
        f"cliente: {contrato['cliente']}"
    )
    r = cliente.chat.completions.create(
        model=CONFIG["potente"],
        temperature=0,
        messages=[
            {"role": "system", "content": P.SISTEMA_VENCIMIENTOS},
            {"role": "user", "content": datos},
        ],
    )
    return r.choices[0].message.content.strip()


def verificar_formato_expediente(expediente: dict) -> bool:
    r = cliente.chat.completions.create(
        model=CONFIG["barato"],
        messages=[
            {"role": "system", "content": P.SISTEMA_EXPEDIENTE},
            {"role": "user", "content": json.dumps(expediente, ensure_ascii=False)},
        ],
    )
    return r.choices[0].message.content.startswith("VALIDO")


def resumir_clausulas(texto_contrato: str) -> str:
    r = cliente.chat.completions.create(
        model=CONFIG["potente"],
        messages=[
            {"role": "system", "content": P.SISTEMA_CLAUSULAS},
            {"role": "user", "content": texto_contrato},
        ],
    )
    return r.choices[0].message.content


def extraer_partes_contrato(texto_contrato: str) -> list[str]:
    r = cliente.chat.completions.create(
        model=CONFIG["barato"],
        temperature=0,
        max_tokens=120,
        messages=[
            {"role": "system", "content": P.SISTEMA_PARTES},
            {"role": "user", "content": texto_contrato[:6000]},
        ],
    )
    return [l for l in r.choices[0].message.content.splitlines() if l.strip()]


def traducir_aviso(aviso: str) -> str:
    r = cliente.chat.completions.create(
        model=CONFIG["barato"],
        messages=[
            {"role": "system", "content": P.SISTEMA_TRADUCCION},
            {"role": "user", "content": aviso},
        ],
    )
    return r.choices[0].message.content
