import os

GEMINI_PRO = os.getenv("NEWSROOM_PRO_MODEL", "gemini-2.5-pro")
GEMINI_FLASH = os.getenv("NEWSROOM_FLASH_MODEL", "gemini-2.5-flash")
LITELLM_MODEL = os.getenv("NEWSROOM_LITELLM_MODEL", "gpt-4o")
REQUIRED_CMS_FIELDS = ("slug", "headline", "byline", "body", "section")
