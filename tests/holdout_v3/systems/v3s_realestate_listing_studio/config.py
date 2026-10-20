import os

MODELOS = {
    "redaccion": os.environ.get("INMO_MODELO_REDACCION", "gpt-4o"),
    "ligero": os.environ.get("INMO_MODELO_LIGERO", "gpt-4o-mini"),
    "chat": os.environ.get("INMO_MODELO_CHAT", "gpt-4o"),
}
CHROMA_DIR = os.environ.get("INMO_CHROMA_DIR", ".chroma_listings")
COLECCION = "propiedades"
