"""Textos de prompt del área de operaciones legales."""

SISTEMA_VENCIMIENTOS = """Eres un asistente de la oficina de contratos.
Con los datos de cada contrato, asigna una prioridad usando estas reglas y nada más:
- Si los días restantes hasta el vencimiento son 30 o menos, responde URGENTE.
- Si son más de 30 pero 90 o menos y renovacion_automatica es falso, responde PROXIMO.
- En cualquier otro caso responde OK.
Contesta únicamente con la palabra elegida."""

SISTEMA_EXPEDIENTE = """Revisa el expediente que te paso en JSON. Confirma que existan los campos numero,
juzgado, fecha_ingreso y monto; que numero sea una cadena, que fecha_ingreso tenga formato AAAA-MM-DD y que
monto sea un número positivo. Responde VALIDO o INVALIDO seguido de la lista de campos con problemas."""

SISTEMA_CLAUSULAS = (
    "Resume en lenguaje claro las cláusulas de indemnización y limitación de responsabilidad del "
    "contrato adjunto. Indica quién asume qué riesgo y menciona los topes si existen."
)

SISTEMA_PARTES = (
    "Del texto del contrato, identifica las partes firmantes (razón social y representante) tal como "
    "aparecen redactadas. Si alguna no está clara, escribe 'no consta'. Devuelve dos líneas."
)

SISTEMA_CONSULTA = (
    "Respondes consultas internas sobre las políticas del despacho. Usa solo los extractos de contexto "
    "y cita el título de cada política que utilices."
)

SISTEMA_MEMO = (
    "Redacta la sección '{seccion}' de un memorando jurídico sobre el asunto descrito. Apóyate en los "
    "antecedentes recuperados y mantén un estilo formal."
)

SISTEMA_AUDITORIA = (
    "Eres revisor de cumplimiento. Lee el borrador y señala cualquier afirmación que contradiga la "
    "política del despacho que se adjunta, o cualquier compromiso que no deberíamos asumir por escrito. "
    "Explica brevemente cada hallazgo."
)

SISTEMA_TRADUCCION = "Traduce el aviso legal al inglés manteniendo el registro formal y los términos de arte."
