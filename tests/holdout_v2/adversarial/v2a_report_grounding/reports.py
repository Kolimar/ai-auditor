import json
import anthropic

client = anthropic.Anthropic()

SUMMARY_MODEL = "claude-sonnet-4-5"
REVIEW_MODEL = "claude-sonnet-4-5"


def summarize_incident(source_text: str) -> str:
    msg = client.messages.create(
        model=SUMMARY_MODEL,
        max_tokens=800,
        system="Write a concise incident summary for the on-call handover. Do not invent facts.",
        messages=[{"role": "user", "content": source_text}],
    )
    return msg.content[0].text


def check_claims_supported(source_text: str, summary: str) -> dict:
    msg = client.messages.create(
        model=REVIEW_MODEL,
        max_tokens=600,
        system=(
            "You are a fact checker. For each sentence of the SUMMARY decide whether it is directly supported by the "
            "SOURCE. List unsupported sentences and any claim that contradicts the source. "
            'Answer as JSON: {"unsupported": [..], "contradictions": [..]}'
        ),
        messages=[
            {"role": "user", "content": f"SOURCE:\n{source_text}\n\nSUMMARY:\n{summary}"},
        ],
    )
    return json.loads(msg.content[0].text)


def publish(source_text: str) -> str:
    summary = summarize_incident(source_text)
    verdict = check_claims_supported(source_text, summary)
    if verdict["unsupported"] or verdict["contradictions"]:
        raise ValueError("summary not grounded")
    return summary
