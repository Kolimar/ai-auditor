import json
import logging
from openai import OpenAI

log = logging.getLogger(__name__)

DEFAULTS = {"model": "gpt-4o", "attempts": 5}


class EntityService:
    def __init__(self, cfg: dict | None = None):
        self.cfg = {**DEFAULTS, **(cfg or {})}
        self.client = OpenAI()

    def _build(self, text: str) -> list[dict]:
        return [
            {"role": "system", "content": "Extract people, organizations and places mentioned in the news excerpt. "
                                          "Reply only with a JSON object with keys people, orgs, places."},
            {"role": "user", "content": text},
        ]

    def extract_entities(self, text: str) -> dict:
        last = None
        for attempt in range(self.cfg["attempts"]):
            resp = self.client.chat.completions.create(
                model=self.cfg["model"],
                messages=self._build(text),
            )
            raw = resp.choices[0].message.content
            try:
                data = json.loads(raw)
                if {"people", "orgs", "places"} <= data.keys():
                    return data
            except json.JSONDecodeError as exc:
                last = exc
                log.warning("bad json on attempt %s", attempt)
        raise RuntimeError(f"extraction failed: {last}")

    def headline(self, text: str) -> str:
        resp = self.client.chat.completions.create(
            model=self.cfg["model"],
            messages=[{"role": "user", "content": "Write an engaging headline for:\n" + text}],
        )
        return resp.choices[0].message.content
