import csv
from typing import Literal

from pydantic import BaseModel
from pydantic_ai import Agent

from prompts import NPS_SYSTEM
from settings import SETTINGS


class ThemeLabel(BaseModel):
    theme: Literal["onboarding", "pricing", "reliability", "support", "missing_feature", "other"]


nps_theme_agent = Agent(SETTINGS.nps_model, output_type=ThemeLabel, system_prompt=NPS_SYSTEM)


def run_nightly_tagging(path: str) -> list[dict]:
    out = []
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            result = nps_theme_agent.run_sync(row["comment"])
            out.append({"response_id": row["response_id"], "theme": result.output.theme})
    return out
