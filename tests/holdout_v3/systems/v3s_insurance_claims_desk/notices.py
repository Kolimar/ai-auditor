import litellm

from settings import SETTINGS


def translate_notice(letter: str, target_language: str) -> str:
    """Policyholders in Quebec and Puerto Rico get the letter in their language."""
    out = litellm.completion(
        model=SETTINGS.models.fallback,
        messages=[
            {
                "role": "system",
                "content": f"Translate the insurance letter into {target_language}. "
                "Keep names, claim references and dollar figures unchanged.",
            },
            {"role": "user", "content": letter},
        ],
        temperature=0.2,
    )
    return out.choices[0].message.content
