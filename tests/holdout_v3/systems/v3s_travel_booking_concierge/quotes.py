from openai import AsyncOpenAI

client = AsyncOpenAI()


async def quote_total(nightly_rate: float, nights: int, city_tax_pct: float, resort_fee: float) -> str:
    resp = await client.responses.create(
        model="gpt-4.1-mini",
        instructions="You are a booking calculator. Show the arithmetic briefly and finish with 'TOTAL: <amount>'.",
        input=(
            f"{nights} nights at {nightly_rate} per night, city tax {city_tax_pct}% on the room charge, "
            f"plus a flat resort fee of {resort_fee}. What does the guest pay in total?"
        ),
    )
    return resp.output_text
