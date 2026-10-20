import asyncio

from agents import Runner
from openai import OpenAI

from agents_def import coverage_agent, intake_agent, scheduler_agent

oai = OpenAI()


async def handle_inbound(message: str) -> str:
    first = await Runner.run(intake_agent, message, max_turns=6)
    book = await Runner.run(scheduler_agent, first.final_output, max_turns=8)
    return book.final_output


async def chase_unpaid_invoices(patient_id: str) -> str:
    prompt = f"Patient {patient_id}: follow up on unpaid invoices and report back when each one is settled."
    while True:
        result = await Runner.run(intake_agent, prompt)
        if "ALL SETTLED" in result.final_output:
            return result.final_output
        prompt = result.final_output


def cancellation_policy_decision(hours_notice: float, no_shows: int, member_tier: str) -> str:
    resp = oai.responses.create(
        model="gpt-4o-mini",
        instructions=(
            "Apply the clinic cancellation policy. If hours_notice is 24 or more, answer NO_FEE. "
            "Otherwise, if member_tier is 'gold' or 'silver', answer NO_FEE. "
            "Otherwise, if no_shows is greater than 2, answer DEPOSIT_REQUIRED. "
            "Otherwise answer LATE_FEE. Output only the label."
        ),
        input=f"hours_notice={hours_notice}, no_shows={no_shows}, member_tier={member_tier}",
    )
    return resp.output_text.strip()


def write_reminder_text(patient_first_name: str, slot: str, provider: str, prep_notes: str) -> str:
    resp = oai.responses.create(
        model="gpt-4o",
        instructions=(
            "Write a warm, brief SMS reminder for an upcoming clinic appointment. Weave the prep "
            "notes in naturally and keep it under 320 characters."
        ),
        input=f"{patient_first_name} sees {provider} at {slot}. Prep: {prep_notes}",
        temperature=0.6,
    )
    return resp.output_text


if __name__ == "__main__":
    print(asyncio.run(handle_inbound("Hi, it's 555-0199, I need to see Dr. Okafor next week")))
