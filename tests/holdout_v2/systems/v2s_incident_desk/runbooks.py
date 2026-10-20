from openai import OpenAI
from pydantic import BaseModel

oai = OpenAI()


class Step(BaseModel):
    title: str
    command: str
    timeout_seconds: int


class Runbook(BaseModel):
    service: str
    steps: list[Step]


def generate_runbook(service: str, failure_description: str, architecture_notes: str) -> Runbook:
    completion = oai.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You are a senior SRE. Draft a recovery runbook for the failure below, "
                "ordered so that the least risky actions come first.",
            },
            {
                "role": "user",
                "content": f"Service: {service}\nFailure: {failure_description}\nArchitecture:\n{architecture_notes}",
            },
        ],
        response_format=Runbook,
    )
    return completion.choices[0].message.parsed


def verify_runbook_shape(runbook: Runbook) -> bool:
    r = oai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": "Check this runbook JSON. Every step must have a title string, a command "
                "string and an integer timeout_seconds greater than zero. Say OK if all steps comply, "
                "otherwise say BAD.\n\n" + runbook.model_dump_json(),
            }
        ],
    )
    return r.choices[0].message.content.strip() == "OK"
