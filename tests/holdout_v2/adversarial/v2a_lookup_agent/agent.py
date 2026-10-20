import anthropic

from settings import LOOKUP

client = anthropic.Anthropic()

TOOLS = [
    {
        "name": "get_account_profile",
        "description": "Fetch the customer's account profile by id.",
        "input_schema": {"type": "object", "properties": {"customer_id": {"type": "string"}}, "required": ["customer_id"]},
    },
    {
        "name": "search_kb",
        "description": "Search the knowledge base.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    {
        "name": "open_ticket",
        "description": "Open a support ticket.",
        "input_schema": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]},
    },
]


def load_profile(customer_id: str):
    return client.messages.create(
        model=LOOKUP["model"],
        max_tokens=LOOKUP["max_tokens"],
        tools=TOOLS,
        tool_choice={"type": "tool", "name": LOOKUP["tool"]},
        messages=[{"role": "user", "content": f"Customer id: {customer_id}"}],
    )


def handle_message(message: str):
    return client.messages.create(
        model=LOOKUP["model"],
        max_tokens=LOOKUP["max_tokens"],
        tools=TOOLS,
        tool_choice={"type": "auto"},
        messages=[{"role": "user", "content": message}],
    )
