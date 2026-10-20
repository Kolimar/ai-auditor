from dataclasses import dataclass

from google import genai

client = genai.Client()

VAT = 0.21
USD_PER_EUR = 1.08


@dataclass
class Line:
    sku: str
    quantity: int
    unit_price_eur: float


def build_total_prompt(lines: list[Line]) -> str:
    rows = "\n".join(f"- {l.sku}: {l.quantity} x {l.unit_price_eur:.2f} EUR" for l in lines)
    return (
        "The assistant multiplies each quantity by its unit price, adds the lines together, applies "
        f"{int(VAT * 100)}% VAT to the sum and restates the grand total in US dollars at {USD_PER_EUR} USD per EUR, "
        "rounded to cents. It replies with the number only.\n" + rows
    )


def grand_total_usd(lines: list[Line]) -> str:
    resp = client.models.generate_content(model="gemini-2.5-flash", contents=build_total_prompt(lines))
    return resp.text.strip()


def thank_you_note(customer_name: str, total_usd: float) -> str:
    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"Write a short, friendly thank-you for {customer_name}, whose order came to {total_usd:.2f} USD.",
    )
    return resp.text
