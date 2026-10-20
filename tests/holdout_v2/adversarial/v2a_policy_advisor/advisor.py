import anthropic
from pathlib import Path

client = anthropic.Anthropic()

POLICY_TEXT = "\n\n".join(p.read_text() for p in sorted(Path("policies").glob("*.md")))


def answer_policy_question(question: str, employee_ctx: str) -> str:
    msg = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=700,
        system=[
            {
                "type": "text",
                "text": "You answer HR policy questions using only the handbook below.\n\n" + POLICY_TEXT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": f"Employee context: {employee_ctx}\nQuestion: {question}"}],
    )
    return msg.content[0].text


def answer_followup(question: str, previous_answer: str) -> str:
    msg = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=700,
        system=[
            {
                "type": "text",
                "text": "You answer HR policy questions using only the handbook below.\n\n" + POLICY_TEXT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {"role": "assistant", "content": previous_answer},
            {"role": "user", "content": question},
        ],
    )
    return msg.content[0].text
