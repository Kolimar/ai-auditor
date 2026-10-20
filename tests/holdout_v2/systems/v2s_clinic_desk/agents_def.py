from agents import Agent

from tools import (
    book_slot,
    check_coverage,
    find_slots,
    get_copay,
    list_open_invoices,
    lookup_patient,
)

intake_agent = Agent(
    name="Intake",
    model="gpt-4o",
    instructions=(
        "You are the front-desk assistant of a family clinic. Talk with the patient about what "
        "they need (a visit, a certificate, a billing question). Look the patient up when they give "
        "a phone number and ask for anything missing. You do not give medical advice; for anything "
        "clinical tell them a nurse will call back."
    ),
    tools=[lookup_patient, list_open_invoices],
)

coverage_agent = Agent(
    name="Coverage Checker",
    model="gpt-4o",
    instructions=(
        "Whenever a request reaches you, call check_coverage first, then call get_copay with the same "
        "arguments, and finally write the result to the patient in two sentences."
    ),
    tools=[check_coverage, get_copay],
)

scheduler_agent = Agent(
    name="Scheduler",
    model="gpt-4o",
    instructions=(
        "Help the patient pick an appointment. Offer slots that match their stated preferences "
        "(mornings, a specific provider, a day they cannot do). Only book after the patient says yes."
    ),
    tools=[find_slots, book_slot],
)

relay_agent = Agent(
    name="Front Desk Relay",
    model="gpt-4o",
    instructions=(
        "You receive the patient's message after Intake. Hand it over to the Scheduler exactly as it "
        "is, without adding or removing anything."
    ),
    handoffs=[scheduler_agent],
)
