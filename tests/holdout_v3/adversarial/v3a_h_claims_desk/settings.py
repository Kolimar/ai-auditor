import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    routing_model: str = os.getenv("CLAIMS_MODEL", "claude-opus-4-1")
    max_tokens: int = 50


SETTINGS = Settings()
