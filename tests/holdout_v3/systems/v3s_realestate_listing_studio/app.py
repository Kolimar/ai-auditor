import json
import sys

from anuncios import clasificar_consulta, generar_descripcion, moderar_texto_anuncio
from consultas import responder_consulta_comprador
from feed import extraer_datos_feed, validar_ficha


def procesar_feed(ruta: str):
    with open(ruta, encoding="utf-8") as f:
        fragmentos = json.load(f)
    for frag in fragmentos:
        ficha = extraer_datos_feed(frag["xml"])
        if not validar_ficha(ficha):
            continue
        texto = generar_descripcion(ficha, frag.get("notas", ""))
        if moderar_texto_anuncio(texto).startswith("PUBLICAR"):
            print(ficha["ref"], texto)


def chat():
    while True:
        try:
            msg = input("comprador> ")
        except EOFError:
            break
        if clasificar_consulta(msg) in {"comprar", "pedir_visita"}:
            print(responder_consulta_comprador(msg))


if __name__ == "__main__":
    procesar_feed(sys.argv[1]) if len(sys.argv) > 1 else chat()
