import anthropic

from prompts import ROUTING_PROMPT
from settings import SETTINGS

client = anthropic.Anthropic()
ROUTES = {"csm_lead", "support_eng", "renewals", "pooled"}


def route_escalation(account: dict) -> str:
    prompt = ROUTING_PROMPT.format(
        tier=account["tier"],
        arr_usd=account["arr_usd"],
        open_p1=account["open_p1_tickets"],
        days_to_renewal=account["days_to_renewal"],
    )
    msg = client.messages.create(
        model=SETTINGS.main_model,
        max_tokens=20,
        messages=[{"role": "user", "content": prompt}],
    )
    queue = msg.content[0].text.strip().lower()
    return queue if queue in ROUTES else "pooled"
