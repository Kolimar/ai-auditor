import re

import anthropic

from prompts import CHURN_PROMPT, QBR_SYSTEM, RENEWAL_EMAIL_PROMPT
from settings import SETTINGS

client = anthropic.Anthropic()


def draft_qbr_narrative(account: dict, metrics: dict, goals: list[str]) -> str:
    facts = "\n".join(f"- {k}: {v}" for k, v in metrics.items())
    goal_text = "; ".join(goals)
    msg = client.messages.create(
        model=SETTINGS.main_model,
        max_tokens=SETTINGS.max_tokens,
        system=QBR_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": f"Customer: {account['name']}\nStated goals: {goal_text}\nQuarter metrics:\n{facts}",
            }
        ],
    )
    return msg.content[0].text


def flag_churn_language(transcript: str) -> str:
    msg = client.messages.create(
        model=SETTINGS.fast_model,
        max_tokens=120,
        messages=[{"role": "user", "content": CHURN_PROMPT.format(transcript=transcript)}],
    )
    return msg.content[0].text.strip()


def write_renewal_email(csm: str, contact: dict, renewal_date: str, sentiment: str, wins: list[str]) -> dict:
    highlights = "\n".join(f"* {w}" for w in wins)
    prompt = RENEWAL_EMAIL_PROMPT.format(
        csm_name=csm,
        contact_name=contact["name"],
        company=contact["company"],
        renewal_date=renewal_date,
        sentiment=sentiment,
        highlights=highlights,
    )
    msg = client.messages.create(
        model=SETTINGS.main_model,
        max_tokens=700,
        messages=[{"role": "user", "content": prompt}],
    )
    text = msg.content[0].text
    subject = re.sub(r"^Subject:\s*", "", text.splitlines()[0]).strip()
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(text.splitlines()[1:])).strip()
    return {"subject": subject, "body": body}


def csm_copilot_repl(account: dict) -> None:
    history = []
    while True:
        question = input("csm> ")
        if question.strip() in {"exit", "quit"}:
            break
        history.append({"role": "user", "content": question})
        msg = client.messages.create(
            model=SETTINGS.main_model,
            max_tokens=800,
            system=f"You help a CSM prepare for calls with {account['name']}. Be brief and practical.",
            messages=history,
        )
        answer = msg.content[0].text
        history.append({"role": "assistant", "content": answer})
        print(answer)
