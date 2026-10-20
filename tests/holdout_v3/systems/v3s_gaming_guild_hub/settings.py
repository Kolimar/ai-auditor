import os

SMART_MODEL = os.environ.get("GUILDHUB_SMART_MODEL", "anthropic/claude-sonnet-4-5")
CHEAP_MODEL = os.environ.get("GUILDHUB_CHEAP_MODEL", "gpt-4o-mini")
MID_MODEL = os.environ.get("GUILDHUB_MID_MODEL", "gpt-4o")
LANGS = ("es", "pt-BR", "de", "ja")
RARITIES = ["common", "uncommon", "rare", "epic", "legendary"]
