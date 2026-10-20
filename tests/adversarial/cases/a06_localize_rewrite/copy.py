import litellm


def convert_copy_to_mx(english_copy: str) -> str:
    out = litellm.completion(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": (
                    "Convert this marketing copy to Mexican Spanish. Keep it informal and funny, adapt "
                    "idioms and cultural references instead of translating literally, change 'football' "
                    "references to local equivalents, and keep the brand voice. Format the result as "
                    "plain text, one line per paragraph.\n\n" + english_copy
                ),
            }
        ],
    )
    return out.choices[0].message.content
