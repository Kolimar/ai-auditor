from openai import OpenAI

client = OpenAI()


def redactar_guia_gastos(departamento: str, tono: str) -> str:
    r = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.8,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Escribe una guia amigable de politica de gastos para el equipo de {departamento}, "
                    f"con un tono {tono}. A modo de ejemplo ilustrativo puedes mencionar situaciones como "
                    "'si el importe supera 1000 euros se necesita aprobacion del responsable', pero inventa "
                    "tus propios casos cotidianos, anecdotas y consejos practicos. Extension: unas 600 palabras."
                ),
            }
        ],
    )
    return r.choices[0].message.content
