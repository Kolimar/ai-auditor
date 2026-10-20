import json
import os

import anthropic
from google import genai
from openai import OpenAI

claude = anthropic.Anthropic()
oai = OpenAI()
gem = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

WRITER_SYSTEM = """You are a features writer for a travel and culture magazine. Write with a distinctive voice:
concrete sensory detail, varied sentence length, no clichés. Follow the brief's angle and word count."""

CRITIC_SYSTEM = """You are the magazine's senior editor. You did not write this piece. Judge it against the house
standards: originality of angle, structural coherence, factual caution (flag claims that need sourcing), and
whether the voice is consistent. Return JSON: {"verdict": "publish" | "revise", "notes": [str]}."""

TRANSLATE_SYSTEM = """Translate the article from English into {language}. Preserve irony, wordplay and register.
Where an idiom has no equivalent, adapt it rather than translating literally, and keep the paragraph structure."""

SUMMARY_SYSTEM = """Summarize the report for an executive audience in at most 400 words. Keep the three most
consequential findings, the main caveats and any figures that drive the conclusions."""

HEADLINE_SYSTEM = """Propose five headlines with distinct angles (curiosity, service, emotional, contrarian, literal)
for the article. One per line, no numbering."""

SLUG_SYSTEM = """Convert the headline into a URL slug: lowercase, ASCII only, words separated by hyphens,
punctuation removed, max 60 characters. Output the slug only."""

DATE_SYSTEM = """Rewrite the publication date given in ISO 8601 as 'Month D, YYYY' in English (for example
'March 4, 2026'). Output only the formatted date."""


def write_draft(brief: dict, revision_notes: list[str] | None = None) -> str:
    user = f"Brief:\n{json.dumps(brief, indent=2)}"
    if revision_notes:
        user += "\n\nEditor notes to address:\n" + "\n".join(f"- {n}" for n in revision_notes)
    msg = claude.messages.create(
        model="claude-opus-5-5",
        max_tokens=4000,
        temperature=0.9,
        system=WRITER_SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text


def critique_draft(draft: str, brief: dict) -> dict:
    msg = claude.messages.create(
        model="claude-sonnet-5-5",
        max_tokens=1200,
        system=CRITIC_SYSTEM,
        messages=[{"role": "user", "content": f"Brief angle: {brief['angle']}\n\nDraft:\n{draft}"}],
    )
    return json.loads(msg.content[0].text)


def translate_article(article: str, language: str) -> str:
    resp = oai.chat.completions.create(
        model="gpt-5.5",
        messages=[
            {"role": "system", "content": TRANSLATE_SYSTEM.format(language=language)},
            {"role": "user", "content": article},
        ],
        temperature=0.4,
    )
    return resp.choices[0].message.content


def summarize_report(report_text: str) -> str:
    resp = gem.models.generate_content(
        model="gemini-2.5-pro",
        contents=[SUMMARY_SYSTEM, report_text],
    )
    return resp.text


def suggest_headlines(article: str) -> list[str]:
    resp = claude.messages.create(
        model="claude-sonnet-5-5",
        max_tokens=300,
        temperature=1.0,
        system=HEADLINE_SYSTEM,
        messages=[{"role": "user", "content": article}],
    )
    return [h.strip() for h in resp.content[0].text.splitlines() if h.strip()]


def make_slug(headline: str) -> str:
    resp = oai.chat.completions.create(
        model="gpt-5.5",
        messages=[
            {"role": "system", "content": SLUG_SYSTEM},
            {"role": "user", "content": headline},
        ],
        temperature=0,
    )
    return resp.choices[0].message.content.strip()


def format_publication_date(iso_date: str) -> str:
    resp = oai.chat.completions.create(
        model="gpt-5.5",
        messages=[
            {"role": "system", "content": DATE_SYSTEM},
            {"role": "user", "content": iso_date},
        ],
        temperature=0,
    )
    return resp.choices[0].message.content.strip()


def produce_article(brief: dict, max_rounds: int = 3) -> dict:
    notes = None
    draft = ""
    for _ in range(max_rounds):
        draft = write_draft(brief, notes)
        review = critique_draft(draft, brief)
        if review["verdict"] == "publish":
            break
        notes = review["notes"]
    headlines = suggest_headlines(draft)
    return {
        "draft": draft,
        "headline": headlines[0],
        "slug": make_slug(headlines[0]),
        "date": format_publication_date(brief["publish_on"]),
        "translations": {lang: translate_article(draft, lang) for lang in brief.get("languages", [])},
    }
