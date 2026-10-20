import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    main_model: str = os.getenv("CS_MAIN_MODEL", "claude-sonnet-4-5")
    fast_model: str = os.getenv("CS_FAST_MODEL", "claude-haiku-4-5")
    nps_model: str = os.getenv("CS_NPS_MODEL", "anthropic:claude-opus-4-1")
    data_dir: str = os.getenv("CS_DATA_DIR", "/var/lib/cs-desk")
    max_tokens: int = int(os.getenv("CS_MAX_TOKENS", "1200"))


SETTINGS = Settings()
