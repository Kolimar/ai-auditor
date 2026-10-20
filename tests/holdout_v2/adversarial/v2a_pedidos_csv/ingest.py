import csv
import json
import anthropic

from config import MODELS, ACTIVE
from prompts import instrucciones_extraccion, cabecera

client = anthropic.Anthropic()


def leer_pedido(fila: str) -> dict:
    mensaje = client.messages.create(
        model=MODELS[ACTIVE],
        max_tokens=300,
        messages=[{"role": "user", "content": instrucciones_extraccion(fila)}],
    )
    return json.loads(mensaje.content[0].text)


def responder_reclamo(texto_cliente: str, pedido: dict) -> str:
    mensaje = client.messages.create(
        model=MODELS[ACTIVE],
        max_tokens=600,
        system=cabecera() + " Responde con empatía y propón una solución concreta.",
        messages=[{"role": "user", "content": f"Pedido: {pedido}\nMensaje del cliente: {texto_cliente}"}],
    )
    return mensaje.content[0].text


def cargar(path: str) -> list[dict]:
    with open(path, newline="") as f:
        return [leer_pedido(";".join(r)) for r in csv.reader(f, delimiter=";")]
