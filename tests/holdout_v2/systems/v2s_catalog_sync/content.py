from google import genai
from google.genai import types

from settings import MODEL_GEMINI, MODEL_GEMINI_VISION

gclient = genai.Client()


def write_product_description(title: str, bullets: list[str], brand_voice: str) -> str:
    prompt = (
        f"Brand voice: {brand_voice}\n"
        f"Product: {title}\n"
        "Key facts:\n" + "\n".join(f"* {b}" for b in bullets) + "\n\n"
        "Write a persuasive description of around 150 words for the product page. "
        "Avoid superlatives we cannot back up."
    )
    out = gclient.models.generate_content(
        model=MODEL_GEMINI,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.8),
    )
    return out.text


def moderate_review(review_text: str) -> str:
    out = gclient.models.generate_content(
        model=MODEL_GEMINI_VISION,
        contents=(
            "Decide whether this customer review may be published. Block it if it contains abuse "
            "aimed at staff, personal data, or claims that the product is dangerous without "
            "evidence. Answer PUBLISH or BLOCK and one short reason.\n\n" + review_text
        ),
    )
    return out.text


def alt_text_for_image(image_bytes: bytes, mime: str = "image/jpeg") -> str:
    out = gclient.models.generate_content(
        model=MODEL_GEMINI_VISION,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime),
            "Describe this product photo for a screen reader in one sentence.",
        ],
    )
    return out.text
