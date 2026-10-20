import os

from pydantic_ai import Agent

from models import PassportData, RefundDecision, RiskNote, SentimentTag

REFUND_PROMPT = """Decide the refund outcome for a cancelled booking.
Inputs are given as fare_class, days_before_departure and booking_channel.
- fare_class Y or B and days_before_departure >= 7: full_refund
- fare_class Y or B and days_before_departure < 7: partial_refund
- any other fare_class: no_refund
- if booking_channel is "corporate" always full_refund."""

refund_decider = Agent(
    os.getenv("REFUND_MODEL", "openai:gpt-4o"),
    output_type=RefundDecision,
    system_prompt=REFUND_PROMPT,
)

passport_extractor = Agent(
    "openai:gpt-4o-mini",
    output_type=PassportData,
    system_prompt=(
        "Read the two machine readable zone lines (MRZ, ICAO 9303 TD3) from the passport scan "
        "and fill in the structured fields."
    ),
)

trip_risk_assessor = Agent(
    "anthropic:claude-sonnet-4-5",
    output_type=RiskNote,
    system_prompt=(
        "Lee los avisos de viaje oficiales y las noticias locales (en inglés o español) y valora el riesgo "
        "para un viajero que visita la ciudad en las fechas indicadas. Distingue entre rumores y hechos confirmados."
    ),
)

review_tagger = Agent(
    "openai:gpt-4o",
    output_type=SentimentTag,
    system_prompt="Tag a hotel review as positive, neutral or negative.",
)


async def should_refund(fare_class: str, days: int, channel: str) -> RefundDecision:
    res = await refund_decider.run(
        f"fare_class={fare_class} days_before_departure={days} booking_channel={channel}"
    )
    return res.output
