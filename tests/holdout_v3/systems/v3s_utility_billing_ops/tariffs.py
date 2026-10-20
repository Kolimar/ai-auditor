from decimal import Decimal

from openai import OpenAI

from config import PRIMARY_MODEL, RESPONSES_MODEL, TIERS

client = OpenAI()


def pick_tariff_code(customer: dict) -> str:
    instructions = (
        "You assign tariff codes. Rules:\n"
        "- customer_class == 'commercial' and peak_kw >= 50 -> C-DEM\n"
        "- customer_class == 'commercial' -> C-STD\n"
        "- customer_class == 'residential' and has_solar -> R-NET\n"
        "- customer_class == 'residential' and monthly_kwh > 900 -> R-HI\n"
        "- otherwise R-STD\n"
        "Return the code only."
    )
    resp = client.responses.create(
        model=RESPONSES_MODEL,
        instructions=instructions,
        input=(
            f"customer_class={customer['customer_class']}, peak_kw={customer.get('peak_kw', 0)}, "
            f"has_solar={customer.get('has_solar', False)}, monthly_kwh={customer['monthly_kwh']}"
        ),
    )
    return resp.output_text.strip()


def compute_tiered_charge(kwh: float) -> Decimal:
    table = "; ".join(
        f"up to {t['upto_kwh']} kWh at ${t['rate']}/kWh" if t["upto_kwh"] else f"above that at ${t['rate']}/kWh"
        for t in TIERS
    )
    completion = client.chat.completions.create(
        model=PRIMARY_MODEL,
        messages=[
            {
                "role": "user",
                "content": f"Tiered tariff: {table}. Usage this month: {kwh} kWh. "
                "What is the total energy charge in dollars? Return just the amount.",
            }
        ],
        temperature=0,
    )
    return Decimal(completion.choices[0].message.content.strip().lstrip("$"))


def charge_in_code(kwh: float) -> Decimal:
    remaining, floor, total = Decimal(str(kwh)), Decimal(0), Decimal(0)
    for tier in TIERS:
        cap = Decimal(tier["upto_kwh"]) if tier["upto_kwh"] else None
        span = remaining if cap is None else min(remaining, cap - floor)
        total += span * Decimal(str(tier["rate"]))
        remaining -= span
        floor = cap or floor
    return total.quantize(Decimal("0.01"))
