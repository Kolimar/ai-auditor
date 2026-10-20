import anthropic

client = anthropic.Anthropic()

SHIPPING_TIERS = [
    ("standard", "5-7 business days", "free over $50"),
    ("express", "2 days", "$12 flat"),
    ("overnight", "next business day", "$25 flat"),
]


def render_shipping_summary() -> str:
    table = "\n".join(f"{n}: {eta}, {price}" for n, eta, price in SHIPPING_TIERS)
    msg = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=300,
        messages=[
            {"role": "user", "content": f"Write a friendly two-sentence summary of these shipping options:\n{table}"}
        ],
    )
    return msg.content[0].text


def handle_checkout_page(request: dict) -> dict:
    return {
        "cart": request["cart"],
        "shipping_blurb": render_shipping_summary(),
    }
