import asyncio

from openai import AsyncOpenAI

client = AsyncOpenAI()
limiter = asyncio.Semaphore(8)


async def write_listing_blurb(listing: dict) -> str:
    async with limiter:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.8,
            messages=[
                {"role": "system", "content": "Write an enticing 80 word property listing blurb from the agent's notes."},
                {"role": "user", "content": listing["agent_notes"]},
            ],
        )
    return resp.choices[0].message.content


async def blurbs_for_portfolio(listings: list[dict]) -> list[str]:
    return await asyncio.gather(*(write_listing_blurb(item) for item in listings))
