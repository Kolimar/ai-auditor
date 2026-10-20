import csv
import json

from openai import OpenAI

cliente = OpenAI()


def extraer_envio(linea: str) -> dict:
    respuesta = cliente.chat.completions.create(
        model="gpt-4o",
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "De cada línea del manifiesto saca el código de seguimiento, el peso en kg, la ciudad de destino "
                    "y la fecha de entrega. Responde en JSON con las claves tracking, peso_kg, destino, fecha."
                ),
            },
            {"role": "user", "content": linea},
        ],
    )
    return json.loads(respuesta.choices[0].message.content)


def cargar_manifiesto(ruta: str):
    with open(ruta, newline="") as f:
        for fila in csv.reader(f, delimiter=";"):
            yield extraer_envio(";".join(fila))


def redactar_aviso_retraso(envio: dict, motivo: str) -> str:
    r = cliente.chat.completions.create(
        model="gpt-4o",
        temperature=0.7,
        messages=[
            {"role": "system", "content": "Escribe un aviso amable y empático al cliente por el retraso de su envío."},
            {"role": "user", "content": f"Envío {envio['tracking']} a {envio['destino']}. Motivo: {motivo}"},
        ],
    )
    return r.choices[0].message.content
