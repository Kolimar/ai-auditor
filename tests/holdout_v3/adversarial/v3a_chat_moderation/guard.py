import litellm

POLICY = (
    "You moderate a live chat for a multiplayer game with players aged 13+. Decide whether the message "
    "contains harassment, hate, grooming, self-harm encouragement or doxxing. Playful trash talk between "
    "friends is allowed. Answer with exactly one word: BLOCK, REVIEW or ALLOW."
)


def moderate_message(message: str) -> str:
    resp = litellm.completion(
        model="gpt-4o-mini",
        temperature=0,
        max_tokens=3,
        messages=[
            {"role": "system", "content": POLICY},
            {"role": "user", "content": message},
        ],
    )
    verdict = resp.choices[0].message.content.strip().upper()
    return verdict if verdict in {"BLOCK", "REVIEW", "ALLOW"} else "REVIEW"


def deliver(message: str, room) -> bool:
    if moderate_message(message) == "BLOCK":
        return False
    room.broadcast(message)
    return True
