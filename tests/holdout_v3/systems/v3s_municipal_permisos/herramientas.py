from agents import function_tool


@function_tool
def consultar_normativa(tema: str) -> str:
    """Busca articulos de la ordenanza de obras y licencias relacionados con el tema."""
    from normativa_index import buscar
    return "\n\n".join(buscar(tema, limite=4))


@function_tool
def estado_expediente(numero: str) -> str:
    """Devuelve el estado actual de un expediente a partir de su numero."""
    from registro import db
    fila = db.fetch_one("SELECT estado, fecha FROM expedientes WHERE numero = %s", (numero,))
    return f"{fila['estado']} desde {fila['fecha']}" if fila else "expediente no encontrado"


@function_tool
def buscar_oficina(servicio: str) -> str:
    """Indica la oficina y el horario que atienden un servicio."""
    from registro import db
    fila = db.fetch_one("SELECT sede, horario FROM oficinas WHERE servicio = %s", (servicio,))
    return f"{fila['sede']} ({fila['horario']})" if fila else "sin datos"
