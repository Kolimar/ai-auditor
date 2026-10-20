from openai import OpenAI

client = OpenAI()

FEW_SHOT = [
    {"role": "user", "content": "Product: cold brew concentrate. Brand voice: playful."},
    {"role": "assistant", "content": "Wake up on the cool side of morning."},
    {"role": "user", "content": "Product: standing desk. Brand voice: premium."},
    {"role": "assistant", "content": "Elevate the way you work."},
    {"role": "user", "content": "Product: trail running shoes. Brand voice: rugged."},
    {"role": "assistant", "content": "Built for the mud between you and the summit."},
]


def write_slogan(product: str, voice: str) -> str:
    resp = client.chat.completions.create(
        model="gpt-4o",
        temperature=1.0,
        messages=[
            {"role": "system", "content": "You are a senior copywriter. Produce one original slogan."},
            *FEW_SHOT,
            {"role": "user", "content": f"Product: {product}. Brand voice: {voice}."},
        ],
    )
    return resp.choices[0].message.content
