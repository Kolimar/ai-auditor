import os
from openai import OpenAI

from modelos import Gasto
from politica import REGLAS, render

cliente = OpenAI()
MODELO = os.getenv("EXPENSE_MODEL", "gpt-4o")


def decidir_gasto(g: Gasto) -> str:
    r = cliente.chat.completions.create(
        model=MODELO,
        temperature=0,
        messages=[
            {"role": "system", "content": REGLAS + "\nResponde solo: aprobar, rechazar o revision."},
            {"role": "user", "content": render(g)},
        ],
    )
    return r.choices[0].message.content.strip().lower()


def nota_al_empleado(g: Gasto, decision: str, comentario_jefe: str) -> str:
    r = cliente.chat.completions.create(
        model=MODELO,
        messages=[{
            "role": "user",
            "content": f"Redacta un mensaje amable para {g.empleado} comunicando la decision '{decision}'. "
                       f"Ten en cuenta el comentario de su jefe: {comentario_jefe}",
        }],
    )
    return r.choices[0].message.content
