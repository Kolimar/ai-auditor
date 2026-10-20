import json
import os

import anthropic

from prompts import WEBHOOK_EXTRACT

MODELS = {
    "light": "claude-haiku-4-5",
    "main": "claude-sonnet-4-5",
}

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def normalize_ats_event(payload: dict) -> dict:
    """Webhook bodies look like
    {"event": "application.created", "data": {"candidate": {"id": "...", "email": "..."},
     "stage": {"name": "..."}, "created_at": "..."}}
    """
    resp = client.messages.create(
        model=MODELS["light"],
        max_tokens=300,
        messages=[
            {
                "role": "user",
                "content": f"{WEBHOOK_EXTRACT}\n\n{json.dumps(payload)}",
            }
        ],
    )
    return json.loads(resp.content[0].text)


def summarize_resume_for_panel(cv_text: str) -> str:
    from prompts import PANEL_BRIEF

    resp = client.messages.create(
        model=MODELS["main"],
        max_tokens=400,
        system=PANEL_BRIEF,
        messages=[{"role": "user", "content": cv_text}],
    )
    return resp.content[0].text
