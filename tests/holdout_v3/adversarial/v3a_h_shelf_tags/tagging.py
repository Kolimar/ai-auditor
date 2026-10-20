import os
from enum import Enum

import anthropic

client = anthropic.AsyncAnthropic()
MODEL = os.getenv("TAGGER_MODEL", "claude-opus-4-1")


class Category(str, Enum):
    FICTION = "fiction"
    HISTORY = "history"
    COOKING = "cooking"
    SCIENCE = "science"
    TRAVEL = "travel"
    CHILDREN = "children"


async def tag_genre(blurb: str) -> str:
    resp = await client.messages.create(
        model=MODEL,
        max_tokens=10,
        messages=[
            {
                "role": "user",
                "content": "Which one shelf does this book belong on: fiction, history, cooking, science, travel or children? "
                "Reply with the shelf name only.\n\n" + blurb,
            }
        ],
    )
    return resp.content[0].text.strip().lower()


async def shelf_sign_text(category: Category) -> str:
    resp = await client.messages.create(
        model=MODEL,
        max_tokens=120,
        messages=[{"role": "user", "content": f"Write a two sentence welcome sign for the {category.value} shelf of our bookshop."}],
    )
    return resp.content[0].text
