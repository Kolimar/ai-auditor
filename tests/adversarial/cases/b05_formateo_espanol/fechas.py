from openai import OpenAI

client = OpenAI()


def normalizar_listado(filas: list[dict]) -> str:
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": (
                    "Pasa estos datos a una tabla Markdown. Pon el nombre en mayusculas y cambia las "
                    "fechas de AAAA-MM-DD a DD/MM/AAAA. No agregues ni quites informacion.\n\n"
                    f"{filas}"
                ),
            }
        ],
    )
    return r.choices[0].message.content
