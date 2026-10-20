import litellm

from settings import CHEAP_MODEL, LANGS, RARITIES, SMART_MODEL


def build_leaderboard_blurb(rows: list[dict]) -> str:
    payload = "\n".join(f"{r['rank']},{r['gamertag']},{r['score']}" for r in rows[:10])
    resp = litellm.completion(
        model=SMART_MODEL,
        messages=[
            {
                "role": "user",
                "content": "Turn these rank,gamertag,score lines into a Markdown table with the "
                "header Rank | Player | Score, one row per line, same order:\n" + payload,
            }
        ],
    )
    return resp.choices[0].message.content


def describe_item_rarity(rarity: str) -> str:
    assert rarity in RARITIES
    resp = litellm.completion(
        model=CHEAP_MODEL,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": "Write a one-sentence shop tooltip, in the voice of a gruff dwarven "
                "merchant, explaining what the item rarity tier means for drop rates and trading.",
            },
            {"role": "user", "content": f"Tier: {rarity}"},
        ],
    )
    return resp.choices[0].message.content.strip()


def render_shop_page(items: list[dict]) -> list[dict]:
    cards = []
    for item in items:
        cards.append({**item, "tooltip": describe_item_rarity(item["rarity"])})
    return cards


def localize_announcement(text: str) -> dict[str, str]:
    out = {}
    for lang in LANGS:
        resp = litellm.completion(
            model=CHEAP_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": f"Translate this game announcement to {lang}. Keep item and map names "
                    f"in English.\n\n{text}",
                }
            ],
        )
        out[lang] = resp.choices[0].message.content
    return out
