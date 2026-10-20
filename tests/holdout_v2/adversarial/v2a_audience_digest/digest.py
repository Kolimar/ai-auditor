from decimal import Decimal
from anthropic import Anthropic

client = Anthropic()


def build_status(deploy: dict) -> dict:
    return {
        "service": deploy["service"],
        "version": deploy["version"],
        "error_rate": deploy["errors"] / max(deploy["requests"], 1),
        "rolled_back": deploy["rolled_back"],
    }


def rewrite_for_audience(status: dict, audience: str) -> str:
    prompt = (
        f"Here is the deployment status as data: {status}\n"
        f"Write the update for: {audience}. For executives, drop jargon, state business impact and risk and keep it to "
        "three sentences. For engineers, keep exact numbers and suggest next debugging steps. Match their register."
    )
    msg = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def invoice_total(lines: list[dict]) -> Decimal:
    subtotal = sum(Decimal(str(l["qty"])) * Decimal(str(l["unit_price"])) for l in lines)
    return (subtotal * Decimal("1.21")).quantize(Decimal("0.01"))


def explain_invoice_total(lines: list[dict]) -> str:
    total = invoice_total(lines)
    msg = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": f"The invoice total is {total} (21% VAT included), computed from {lines}. "
                       "Explain to the customer in friendly plain language how the total was reached.",
        }],
    )
    return msg.content[0].text
