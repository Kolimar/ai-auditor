import json

from google import genai
from google.genai import types

from conf import GEMINI_FLASH, GEMINI_PRO, REQUIRED_CMS_FIELDS
from prompts import BACKGROUND_PROMPT, CMS_CHECK_PROMPT, DIGEST_PROMPT, METADATA_PROMPT, SUMMARY_PROMPT

gclient = genai.Client()


def extract_story_metadata(newsml: str) -> dict:
    resp = gclient.models.generate_content(
        model=GEMINI_FLASH,
        contents=[METADATA_PROMPT, newsml],
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0),
    )
    return json.loads(resp.text)


def verify_article_record(record: dict) -> bool:
    resp = gclient.models.generate_content(
        model=GEMINI_FLASH,
        contents=f"{CMS_CHECK_PROMPT}\nRequired: {', '.join(REQUIRED_CMS_FIELDS)}\n\n{json.dumps(record)}",
    )
    return resp.text.strip().startswith("VALID")


def build_markdown_digest(stories: list[dict]) -> str:
    resp = gclient.models.generate_content(
        model=GEMINI_FLASH,
        contents=DIGEST_PROMPT + "\n\n" + json.dumps(stories, indent=2),
    )
    return resp.text


def summarize_wire_story(text: str) -> str:
    resp = gclient.models.generate_content(
        model=GEMINI_PRO,
        contents=[SUMMARY_PROMPT, text],
    )
    return resp.text


def research_background(topic: str) -> list[str]:
    notes = []
    while True:
        resp = gclient.models.generate_content(
            model=GEMINI_PRO,
            contents=[BACKGROUND_PROMPT, f"Topic: {topic}", "Notes so far:\n" + "\n".join(notes)],
        )
        notes.append(resp.text)
        if "DONE" in resp.text:
            return notes
