import litellm
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from settings import CHEAP_MODEL, MID_MODEL

MOD_SYSTEM = """You moderate in-game chat for a competitive team shooter with a young audience.
Mark a message BLOCK if it contains harassment, slurs (including disguised spellings), doxxing,
grooming signals or credible threats. Trash talk about gameplay is fine. Otherwise ALLOW.
Respond with BLOCK or ALLOW and a short reason after a dash."""


@retry(
    retry=retry_if_exception_type((litellm.RateLimitError, litellm.APIConnectionError)),
    wait=wait_exponential(multiplier=1, max=20),
    stop=stop_after_attempt(5),
)
def moderate_chat_message(message: str, channel: str) -> tuple[bool, str]:
    resp = litellm.completion(
        model=CHEAP_MODEL,
        messages=[
            {"role": "system", "content": MOD_SYSTEM},
            {"role": "user", "content": f"[{channel}] {message}"},
        ],
        temperature=0,
    )
    text = resp.choices[0].message.content.strip()
    verdict, _, reason = text.partition("-")
    return verdict.strip().upper() == "BLOCK", reason.strip()


def decide_ban_appeal(appeal: dict) -> str:
    prompt = (
        "Decide the outcome of this ban appeal using the policy table.\n\n"
        "| condition | outcome |\n"
        "| offence in (spam, language) and strikes < 3 and account_age_days > 30 | reduce |\n"
        "| offence == cheating | uphold |\n"
        "| offence == payment_fraud | escalate |\n"
        "| strikes >= 3 | uphold |\n"
        "| everything else | review |\n\n"
        f"offence={appeal['offence']}\nstrikes={appeal['strikes']}\n"
        f"account_age_days={appeal['account_age_days']}\n"
        "Answer with one word: reduce, uphold, escalate or review."
    )
    resp = litellm.completion(
        model=MID_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=5,
    )
    return resp.choices[0].message.content.strip().lower()
