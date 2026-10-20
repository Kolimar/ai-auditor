def cabecera() -> str:
    return "Eres un asistente de logística de una tienda en línea."


def instrucciones_extraccion(fila: str) -> str:
    return (
        cabecera()
        + "\nRecibirás una línea de un archivo de exportación separada por punto y coma, con las columnas "
        "id_pedido;fecha;sku;cantidad;importe. Devuelve un JSON con id_pedido, fecha (YYYY-MM-DD), sku, "
        "cantidad e importe.\n\nLínea: "
        + fila
    )
