from dataclasses import dataclass, field

import anthropic

from prompts import DECLINE_STYLE, OFFER_ARITHMETIC, SCREEN_RULES

client = anthropic.Anthropic()


@dataclass
class Candidate:
    name: str
    country: str
    years_experience: float
    skills: list[str] = field(default_factory=list)


def screen_candidate(c: Candidate) -> str:
    msg = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=5,
        temperature=0,
        system=SCREEN_RULES,
        messages=[
            {
                "role": "user",
                "content": (
                    f"country: {c.country}\n"
                    f"years_experience: {c.years_experience}\n"
                    f"skills: {', '.join(c.skills)}"
                ),
            }
        ],
    )
    verdict = msg.content[0].text.strip().upper()
    assert verdict in {"ADVANCE", "REJECT", "HOLD"}
    return verdict


def quote_offer_total(base: float, bonus_pct: float, signing: float, relocation: float) -> str:
    msg = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=40,
        system=OFFER_ARITHMETIC,
        messages=[
            {
                "role": "user",
                "content": (
                    f"base salary: {base}\nbonus percentage: {bonus_pct}\n"
                    f"signing bonus: {signing}\nrelocation allowance: {relocation}"
                ),
            }
        ],
    )
    return msg.content[0].text


def draft_decline_note(candidate_name: str, feedback_points: list[str]) -> str:
    bullets = "\n".join(f"- {p}" for p in feedback_points)
    msg = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=500,
        temperature=0.7,
        system=DECLINE_STYLE,
        messages=[{"role": "user", "content": f"Candidate: {candidate_name}\nFeedback:\n{bullets}"}],
    )
    return msg.content[0].text
