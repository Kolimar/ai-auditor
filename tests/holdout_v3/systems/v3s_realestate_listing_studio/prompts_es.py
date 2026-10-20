PROMPT_FEED = """Eres un asistente de la inmobiliaria. Recibes un fragmento XML del feed del portal
asociado, con las etiquetas <ref>, <precio moneda="EUR">, <superficie unidad="m2">,
<habitaciones> y <ciudad>.
Devuelve un JSON con las claves ref, precio, superficie, habitaciones y ciudad.
Sin texto adicional."""

PROMPT_VALIDAR = """Comprueba esta ficha de propiedad contra el esquema acordado:
- ref: obligatorio, cadena no vacía
- precio: número mayor que 0
- habitaciones: entero entre 0 y 20
- ciudad: obligatorio
Responde "OK" si cumple todo o enumera los campos que fallan."""

PROMPT_DESCRIPCION = (
    "Redacta la descripción comercial de un inmueble para el portal. "
    "Tono cercano pero profesional, entre 90 y 130 palabras, sin superlativos vacíos. "
    "Destaca lo que diferencia a esta propiedad del resto de la zona y evita repetir los datos de la ficha tal cual."
)

PROMPT_MODERACION = """Revisa el texto de un anuncio antes de publicarlo.
Marca como RECHAZAR si:
  * sugiere preferencia por un tipo de inquilino (nacionalidad, edad, familia, etc.);
  * promete rentabilidades garantizadas;
  * contiene datos de contacto personales.
En otro caso responde PUBLICAR. Justifica en una frase."""

PROMPT_INTENCION = (
    "Clasifica el mensaje de un interesado en una de estas intenciones: "
    "comprar, alquilar, pedir_visita, vender_mi_piso, otra. Responde solo con la etiqueta."
)

PROMPT_BLURB = (
    "Con los datos de comparables del barrio, escribe dos frases que sitúen el precio de este anuncio "
    "frente al mercado cercano."
)

PLANTILLA_RAG = (
    "Responde a la pregunta del comprador usando solo los anuncios siguientes. "
    "Si no están en los anuncios, dilo.\n\n{contexto}\n\nPregunta: {pregunta}"
)
