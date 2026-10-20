import json
import os

from google import genai
from google.genai import types

cliente = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MODELO_PRO = "gemini-2.5-pro"

PROMPT_PRIORIDAD = """Eres el asignador de prioridad de la mesa de ayuda de Soluciones Andinas.
Recibes un JSON con los campos del cliente. Responde solo con ALTA, MEDIA o BAJA según estas reglas:
1. ALTA si el campo plan es "corporativo" y horas_sla_restantes es menor que 6.
2. ALTA si caida_servicio es verdadero.
3. MEDIA si tickets_abiertos es 3 o más.
4. MEDIA si el importe_reclamado supera 800.
5. BAJA en cualquier otro caso."""

PROMPT_EXTRACCION = """Del siguiente JSON de la pasarela de pagos extrae nombre_cliente, correo, numero_pedido,
importe y moneda. Devuelve un JSON con exactamente esas claves y nada más."""

PROMPT_FECHA = """Convierte la fecha que recibes en formato AAAA-MM-DD al formato "D de mes de AAAA" en español,
con el mes en minúsculas (por ejemplo, "4 de marzo de 2026"). Responde solo con la fecha."""

PROMPT_QUEJA = """Lee el mensaje del cliente. Indica si en el fondo es una queja seria o solo un comentario
irónico o exagerado. Presta atención a la ironía, el sarcasmo y la cortesía que oculta enfado
("qué rapidez tan admirable, solo tardaron tres semanas"). Responde con JSON:
{"tipo": "queja_seria" | "ironia_leve" | "neutral", "motivo": "<una frase>"}."""

PROMPT_RESPUESTA = """Redacta la respuesta al cliente en español neutro. Muestra empatía concreta con su situación,
reconoce el error si es nuestro, explica el siguiente paso con claridad y evita fórmulas vacías.
Máximo 150 palabras.
Nombre: {nombre}
Prioridad: {prioridad}
Tipo de mensaje: {tipo}
Mensaje:
{mensaje}"""

PROMPT_HILO = """Resume el hilo de correos para la persona que toma el caso: qué se pidió, qué se prometió
y quién debe hacer qué. Señala contradicciones entre mensajes. Hilo:

{hilo}"""


def clasificar_prioridad(campos: dict) -> str:
    respuesta = cliente.models.generate_content(
        model=MODELO_PRO,
        contents=PROMPT_PRIORIDAD + "\n\n" + json.dumps(campos, ensure_ascii=False),
        config=types.GenerateContentConfig(temperature=0),
    )
    return respuesta.text.strip()


def extraer_campos_pago(payload: dict) -> dict:
    respuesta = cliente.models.generate_content(
        model=MODELO_PRO,
        contents=PROMPT_EXTRACCION + "\n\n" + json.dumps(payload, ensure_ascii=False),
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return json.loads(respuesta.text)


def formatear_fecha(fecha_iso: str) -> str:
    respuesta = cliente.models.generate_content(
        model=MODELO_PRO,
        contents=PROMPT_FECHA + "\n\n" + fecha_iso,
        config=types.GenerateContentConfig(temperature=0),
    )
    return respuesta.text.strip()


def interpretar_mensaje(mensaje: str) -> dict:
    respuesta = cliente.models.generate_content(
        model=MODELO_PRO,
        contents=PROMPT_QUEJA + "\n\nMensaje:\n" + mensaje,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return json.loads(respuesta.text)


def redactar_respuesta(nombre: str, prioridad: str, tipo: str, mensaje: str) -> str:
    prompt = PROMPT_RESPUESTA.format(nombre=nombre, prioridad=prioridad, tipo=tipo, mensaje=mensaje)
    respuesta = cliente.models.generate_content(
        model=MODELO_PRO,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.7),
    )
    return respuesta.text


def resumir_hilo(correos: list[str]) -> str:
    respuesta = cliente.models.generate_content(
        model=MODELO_PRO,
        contents=PROMPT_HILO.format(hilo="\n---\n".join(correos)),
        config=types.GenerateContentConfig(temperature=0.2),
    )
    return respuesta.text.strip()


def atender(payload: dict, campos_cliente: dict, mensaje: str, correos: list[str]) -> dict:
    pago = extraer_campos_pago(payload)
    prioridad = clasificar_prioridad(campos_cliente)
    mensaje_tipo = interpretar_mensaje(mensaje)
    if mensaje_tipo["tipo"] == "queja_seria" and prioridad == "BAJA":
        prioridad = "MEDIA"
    fecha = formatear_fecha(payload["fecha_pedido"])
    borrador = redactar_respuesta(pago["nombre_cliente"], prioridad, mensaje_tipo["tipo"], mensaje)
    contexto = resumir_hilo(correos) if correos else ""
    return {"prioridad": prioridad, "fecha": fecha, "respuesta": borrador, "contexto": contexto}
