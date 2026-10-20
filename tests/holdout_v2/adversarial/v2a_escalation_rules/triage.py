from openai import OpenAI

client = OpenAI()

ESCALATION_PROMPT = """You review the latest customer message in a support thread and decide the routing.

Escalate to a human lead if ANY of the following holds:
- the customer has complained about the same problem more than twice in the thread
- the tone is hostile, threatening, or mentions legal action
- the customer says they will cancel, even implicitly or sarcastically
Otherwise answer "keep_bot".

Reply with exactly one token: escalate or keep_bot.

Thread:
{thread}
"""


def route_thread(messages: list[str]) -> str:
    thread = "\n".join(f"- {m}" for m in messages[-12:])
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        max_tokens=4,
        messages=[{"role": "user", "content": ESCALATION_PROMPT.format(thread=thread)}],
    )
    return resp.choices[0].message.content.strip()


def draft_reply(messages: list[str], agent_name: str) -> str:
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": f"You are {agent_name}, a friendly support agent. Write a helpful, empathetic reply."},
            {"role": "user", "content": "\n".join(messages)},
        ],
    )
    return resp.choices[0].message.content
