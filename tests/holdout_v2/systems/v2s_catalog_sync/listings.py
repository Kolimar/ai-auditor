import json

import litellm

from settings import FX_TO_EUR, MODEL_FAST, MODEL_TEXT, Category, label_for

CATEGORY_NAMES = [c.value for c in Category]


def convert_listing_units(item: dict) -> dict:
    prompt = (
        "Supplier data arrives in imperial units and foreign currency. Convert weight_oz to grams "
        "(1 oz = 28.3495 g), length_in to centimetres (1 in = 2.54 cm) and price to EUR using the "
        f"rates {FX_TO_EUR}. Round grams to integer and the price to two decimals. Reply with JSON "
        "having keys weight_g, length_cm, price_eur.\n\n"
        f"weight_oz={item['weight_oz']} length_in={item['length_in']} "
        f"price={item['price']} currency={item['currency']}"
    )
    resp = litellm.completion(
        model=MODEL_TEXT,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


def render_spec_table(specs: dict) -> str:
    resp = litellm.completion(
        model=MODEL_FAST,
        messages=[
            {
                "role": "user",
                "content": (
                    "Turn this JSON of product specifications into a Markdown table with the columns "
                    "Attribute and Value. Keep the order of the keys and do not add or drop rows.\n"
                    + json.dumps(specs)
                ),
            }
        ],
    )
    return resp.choices[0].message.content


def assign_category(title: str) -> str:
    resp = litellm.completion(
        model=MODEL_TEXT,
        temperature=0,
        max_tokens=10,
        messages=[
            {
                "role": "system",
                "content": "Place the product title into exactly one of these categories: "
                + ", ".join(CATEGORY_NAMES)
                + ". Answer with the category name only.",
            },
            {"role": "user", "content": title},
        ],
    )
    return resp.choices[0].message.content.strip().lower()


def category_banner_text(category: Category) -> str:
    resp = litellm.completion(
        model=MODEL_TEXT,
        messages=[
            {
                "role": "user",
                "content": f"Write a two-sentence welcome blurb for the '{label_for(category)}' "
                "section of our online shop. Friendly, no exclamation marks.",
            }
        ],
    )
    return resp.choices[0].message.content
