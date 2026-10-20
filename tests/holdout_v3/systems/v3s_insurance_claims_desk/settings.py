"""Runtime configuration for the claims desk."""
import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModelTiers:
    heavy: str = os.getenv("CLAIMS_HEAVY_MODEL", "claude-opus-4-1")
    standard: str = os.getenv("CLAIMS_STD_MODEL", "claude-sonnet-4-5")
    fallback: str = os.getenv("CLAIMS_FALLBACK_MODEL", "gpt-4o-mini")


@dataclass
class Settings:
    models: ModelTiers = field(default_factory=ModelTiers)
    max_tokens: int = 1024
    inbox_path: str = os.getenv("CLAIMS_INBOX", "data/claims_inbox.jsonl")
    out_dir: str = os.getenv("CLAIMS_OUT", "out")


SETTINGS = Settings()
