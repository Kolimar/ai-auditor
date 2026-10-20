import anthropic
import prompts

client = anthropic.Anthropic()


def decide_refund(order_total: float, days: int, returned: bool) -> str:
    body = prompts.REFUND_HEADER + prompts.REFUND_RULES + prompts.REFUND_INPUT.format(
        order_total=order_total, days=days, returned=str(returned).lower()
    )
    msg = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=8,
        messages=[{"role": "user", "content": body}],
    )
    return msg.content[0].text.strip()
