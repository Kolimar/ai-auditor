import litellm

from conf import LITELLM_MODEL
from prompts import EDITOR_CHAT_SYSTEM, FACTCHECK_PROMPT, HEADLINE_PROMPT


def generate_headlines(story: str) -> str:
    out = litellm.completion(
        model=LITELLM_MODEL,
        temperature=0.9,
        messages=[
            {"role": "system", "content": HEADLINE_PROMPT},
            {"role": "user", "content": story},
        ],
    )
    return out.choices[0].message.content


def fact_check_draft(draft: str, sources: list[str]) -> str:
    joined = "\n\n".join(f"[Source {i + 1}]\n{s}" for i, s in enumerate(sources))
    out = litellm.completion(
        model=LITELLM_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": FACTCHECK_PROMPT},
            {"role": "user", "content": f"DRAFT:\n{draft}\n\nSOURCES:\n{joined}"},
        ],
    )
    return out.choices[0].message.content


def editor_chat():
    history = [{"role": "system", "content": EDITOR_CHAT_SYSTEM}]
    while True:
        question = input("night-desk> ").strip()
        if question in {"quit", "exit"}:
            break
        history.append({"role": "user", "content": question})
        out = litellm.completion(model=LITELLM_MODEL, messages=history)
        answer = out.choices[0].message.content
        history.append({"role": "assistant", "content": answer})
        print(answer)
