import anthropic

client = anthropic.Anthropic()


def is_contract_compliant(contract_text: str, regulation_text: str) -> bool:
    msg = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1500,
        thinking={"type": "enabled", "budget_tokens": 1024},
        messages=[
            {
                "role": "user",
                "content": (
                    "Responde solo 'si' o 'no': ¿cumple el contrato la normativa adjunta? Cruza las "
                    "clausulas de subcontratacion, transferencia internacional de datos y plazos de "
                    "notificacion con cada articulo aplicable, considerando definiciones y remisiones "
                    "entre secciones.\n\nCONTRATO:\n" + contract_text +
                    "\n\nNORMATIVA:\n" + regulation_text
                ),
            }
        ],
    )
    answer = [b.text for b in msg.content if b.type == "text"][-1]
    return answer.strip().lower().startswith("si")
