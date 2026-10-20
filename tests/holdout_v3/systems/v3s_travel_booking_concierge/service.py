import asyncio

from agents import Runner

from agents_def import complaint_responder, front_desk, itinerary_writer
from checks import passport_extractor, should_refund
from quotes import quote_total


async def book(request: str, mrz: str):
    passport = await passport_extractor.run(mrz)
    handled = await Runner.run(front_desk, request, max_turns=8)
    return passport.output, handled.final_output


async def itinerary(plan: str) -> str:
    out = await Runner.run(itinerary_writer, plan, max_turns=3)
    return out.final_output


async def reply_to_complaint(text: str) -> str:
    out = await Runner.run(complaint_responder, text, max_turns=2)
    return out.final_output


async def cancel(fare: str, days: int, channel: str, rate: float):
    decision = await should_refund(fare, days, channel)
    fee = await quote_total(rate, 1, 0.0, 0.0)
    return decision, fee


if __name__ == "__main__":
    print(asyncio.run(itinerary("Lisboa 3 noches, vuelo TP123, hotel Baixa")))
