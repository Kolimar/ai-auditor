from openai import OpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
import openai

from config import MODELOS
from prompts_es import PROMPT_BLURB, PROMPT_DESCRIPCION, PROMPT_INTENCION, PROMPT_MODERACION

cliente = OpenAI()


@retry(
    retry=retry_if_exception_type((openai.RateLimitError, openai.APIConnectionError)),
    stop=stop_after_attempt(4),
    wait=wait_exponential(min=1, max=20),
)
def generar_descripcion(ficha: dict, notas_agente: str) -> str:
    detalle = "; ".join(f"{k}: {v}" for k, v in ficha.items())
    r = cliente.chat.completions.create(
        model=MODELOS["redaccion"],
        temperature=0.8,
        messages=[
            {"role": "system", "content": PROMPT_DESCRIPCION},
            {"role": "user", "content": f"Ficha: {detalle}\nNotas del agente: {notas_agente}"},
        ],
    )
    return r.choices[0].message.content


def moderar_texto_anuncio(texto: str) -> str:
    r = cliente.chat.completions.create(
        model=MODELOS["redaccion"],
        messages=[
            {"role": "system", "content": PROMPT_MODERACION},
            {"role": "user", "content": texto},
        ],
    )
    return r.choices[0].message.content


def clasificar_consulta(mensaje: str) -> str:
    r = cliente.chat.completions.create(
        model=MODELOS["ligero"],
        max_tokens=8,
        messages=[
            {"role": "system", "content": PROMPT_INTENCION},
            {"role": "user", "content": mensaje},
        ],
    )
    return r.choices[0].message.content.strip()


def traducir_anuncio_ingles(texto: str) -> str:
    r = cliente.chat.completions.create(
        model=MODELOS["ligero"],
        messages=[
            {"role": "user", "content": "Translate this property listing to natural British English, "
                                        "keeping the place names in Spanish:\n\n" + texto},
        ],
    )
    return r.choices[0].message.content


def enriquecer_anuncios(anuncios: list[dict], almacen) -> list[dict]:
    salida = []
    for anuncio in anuncios:
        comparables = almacen.similarity_search("precio medio por metro cuadrado en el barrio", k=4)
        bloque = "\n".join(c.page_content for c in comparables)
        r = cliente.chat.completions.create(
            model=MODELOS["ligero"],
            messages=[
                {"role": "system", "content": PROMPT_BLURB},
                {"role": "user", "content": f"Anuncio {anuncio['ref']} a {anuncio['precio']} EUR.\n{bloque}"},
            ],
        )
        anuncio["contexto_mercado"] = r.choices[0].message.content
        salida.append(anuncio)
    return salida
