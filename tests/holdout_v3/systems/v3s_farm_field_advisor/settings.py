import os

GEMINI_PRO = os.getenv("FARM_GEMINI_PRO", "gemini-2.5-pro")
GEMINI_FLASH = os.getenv("FARM_GEMINI_FLASH", "gemini-2.5-flash")
CHAT_MODEL = os.getenv("FARM_CHAT_MODEL", "gpt-4o")
CHROMA_DIR = os.getenv("FARM_CHROMA_DIR", "./chroma_agro")
CROPS = ["citrus", "olive", "almond", "vineyard"]
