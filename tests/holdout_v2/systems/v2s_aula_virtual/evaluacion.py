from google import genai
from google.genai import types

import textos

cliente = genai.Client()
MODELO_PRO = "gemini-2.5-pro"
MODELO_FLASH = "gemini-2.5-flash"


def calcular_nota_final(parcial: float, tareas: float, final: float, faltas: int) -> float:
    r = cliente.models.generate_content(
        model=MODELO_PRO,
        contents=f"{textos.NOTA_FINAL}\n\nparcial={parcial}\ntareas={tareas}\nfinal={final}\nfaltas_injustificadas={faltas}",
        config=types.GenerateContentConfig(temperature=0),
    )
    return float(r.text.strip().replace(",", "."))


def clasificar_pregunta_foro(mensaje: str) -> str:
    r = cliente.models.generate_content(
        model=MODELO_PRO,
        contents=[textos.CLASIFICAR_FORO, mensaje],
    )
    return r.text.strip().lower()


def corregir_ensayo(ensayo: str, rubrica: str) -> str:
    r = cliente.models.generate_content(
        model=MODELO_PRO,
        contents=f"{textos.CORRECCION}\n\nRÚBRICA:\n{rubrica}\n\nENSAYO:\n{ensayo}",
    )
    return r.text


def generar_ejercicios(tema: str, nivel: str, n: int = 5) -> str:
    r = cliente.models.generate_content(
        model=MODELO_PRO,
        contents=textos.EJERCICIOS.format(n=n, tema=tema, nivel=nivel),
        config=types.GenerateContentConfig(temperature=0.9),
    )
    return r.text
