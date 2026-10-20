import anthropic

client = anthropic.Anthropic()


def classify_review_sentiment(review_text: str) -> str:
    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=20,
        system=(
            "Clasifica la reseña como positiva, negativa o mixta. Muchas reseñas usan "
            "sarcasmo o ironía ('Genial, otra vez se rompió al segundo día'); la polaridad "
            "real depende de la intención del autor, no de las palabras. Responde con una sola palabra."
        ),
        messages=[{"role": "user", "content": review_text}],
    )
    return resp.content[0].text.strip().lower()
