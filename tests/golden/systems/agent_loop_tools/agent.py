import json

import anthropic

from backoffice import dispatch_tool

client = anthropic.Anthropic()
MODEL = "claude-sonnet-5-5"

TOOLS = [
    {
        "name": "get_order",
        "description": "Get order in the Larkspur back office system.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Identifier of the target record"}, "reason": {"type": "string", "description": "Why the action is needed"}},
            "required": ["id"],
        },
    },
    {
        "name": "list_orders",
        "description": "List orders in the Larkspur back office system.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Identifier of the target record"}, "reason": {"type": "string", "description": "Why the action is needed"}},
            "required": ["id"],
        },
    },
    {
        "name": "cancel_order",
        "description": "Cancel order in the Larkspur back office system.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Identifier of the target record"}, "reason": {"type": "string", "description": "Why the action is needed"}},
            "required": ["id"],
        },
    },
    {
        "name": "refund_order",
        "description": "Refund order in the Larkspur back office system.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Identifier of the target record"}, "reason": {"type": "string", "description": "Why the action is needed"}},
            "required": ["id"],
        },
    },
    {
        "name": "update_shipping_address",
        "description": "Update shipping address in the Larkspur back office system.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Identifier of the target record"}, "reason": {"type": "string", "description": "Why the action is needed"}},
            "required": ["id"],
        },
    },
    {
        "name": "get_customer",
        "description": "Get customer in the Larkspur back office system.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Identifier of the target record"}, "reason": {"type": "string", "description": "Why the action is needed"}},
            "required": ["id"],
        },
    },
    {
        "name": "update_customer_email",
        "description": "Update customer email in the Larkspur back office system.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Identifier of the target record"}, "reason": {"type": "string", "description": "Why the action is needed"}},
            "required": ["id"],
        },
    },
    {
        "name": "list_tickets",
        "description": "List tickets in the Larkspur back office system.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Identifier of the target record"}, "reason": {"type": "string", "description": "Why the action is needed"}},
            "required": ["id"],
        },
    },
    {
        "name": "get_ticket",
        "description": "Get ticket in the Larkspur back office system.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Identifier of the target record"}, "reason": {"type": "string", "description": "Why the action is needed"}},
            "required": ["id"],
        },
    },
    {
        "name": "close_ticket",
        "description": "Close ticket in the Larkspur back office system.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Identifier of the target record"}, "reason": {"type": "string", "description": "Why the action is needed"}},
            "required": ["id"],
        },
    },
    {
        "name": "add_ticket_note",
        "description": "Add ticket note in the Larkspur back office system.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Identifier of the target record"}, "reason": {"type": "string", "description": "Why the action is needed"}},
            "required": ["id"],
        },
    },
    {
        "name": "get_invoice",
        "description": "Get invoice in the Larkspur back office system.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Identifier of the target record"}, "reason": {"type": "string", "description": "Why the action is needed"}},
            "required": ["id"],
        },
    },
    {
        "name": "list_invoices",
        "description": "List invoices in the Larkspur back office system.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Identifier of the target record"}, "reason": {"type": "string", "description": "Why the action is needed"}},
            "required": ["id"],
        },
    },
    {
        "name": "resend_invoice",
        "description": "Resend invoice in the Larkspur back office system.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Identifier of the target record"}, "reason": {"type": "string", "description": "Why the action is needed"}},
            "required": ["id"],
        },
    },
    {
        "name": "apply_coupon",
        "description": "Apply coupon in the Larkspur back office system.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Identifier of the target record"}, "reason": {"type": "string", "description": "Why the action is needed"}},
            "required": ["id"],
        },
    },
    {
        "name": "get_inventory",
        "description": "Get inventory in the Larkspur back office system.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Identifier of the target record"}, "reason": {"type": "string", "description": "Why the action is needed"}},
            "required": ["id"],
        },
    },
    {
        "name": "list_warehouses",
        "description": "List warehouses in the Larkspur back office system.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Identifier of the target record"}, "reason": {"type": "string", "description": "Why the action is needed"}},
            "required": ["id"],
        },
    },
    {
        "name": "create_return_label",
        "description": "Create return label in the Larkspur back office system.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Identifier of the target record"}, "reason": {"type": "string", "description": "Why the action is needed"}},
            "required": ["id"],
        },
    },
    {
        "name": "get_tracking",
        "description": "Get tracking in the Larkspur back office system.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Identifier of the target record"}, "reason": {"type": "string", "description": "Why the action is needed"}},
            "required": ["id"],
        },
    },
    {
        "name": "schedule_callback",
        "description": "Schedule callback in the Larkspur back office system.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Identifier of the target record"}, "reason": {"type": "string", "description": "Why the action is needed"}},
            "required": ["id"],
        },
    },
    {
        "name": "get_loyalty_balance",
        "description": "Get loyalty balance in the Larkspur back office system.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Identifier of the target record"}, "reason": {"type": "string", "description": "Why the action is needed"}},
            "required": ["id"],
        },
    },
    {
        "name": "adjust_loyalty_points",
        "description": "Adjust loyalty points in the Larkspur back office system.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Identifier of the target record"}, "reason": {"type": "string", "description": "Why the action is needed"}},
            "required": ["id"],
        },
    },
    {
        "name": "search_kb",
        "description": "Search kb in the Larkspur back office system.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Identifier of the target record"}, "reason": {"type": "string", "description": "Why the action is needed"}},
            "required": ["id"],
        },
    },
    {
        "name": "get_product",
        "description": "Get product in the Larkspur back office system.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Identifier of the target record"}, "reason": {"type": "string", "description": "Why the action is needed"}},
            "required": ["id"],
        },
    },
    {
        "name": "list_product_variants",
        "description": "List product variants in the Larkspur back office system.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Identifier of the target record"}, "reason": {"type": "string", "description": "Why the action is needed"}},
            "required": ["id"],
        },
    },
    {
        "name": "flag_fraud_review",
        "description": "Flag fraud review in the Larkspur back office system.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Identifier of the target record"}, "reason": {"type": "string", "description": "Why the action is needed"}},
            "required": ["id"],
        },
    },
    {
        "name": "send_sms",
        "description": "Send sms in the Larkspur back office system.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Identifier of the target record"}, "reason": {"type": "string", "description": "Why the action is needed"}},
            "required": ["id"],
        },
    },
]

SUPPORT_SYSTEM = """You are the resolution agent for Larkspur customer support. Use the available tools to
investigate and resolve the customer's issue. When the issue is resolved, reply with a short confirmation."""

PLAN_SYSTEM = """You decide how to resolve a customer issue that may involve several policies at once
(partial refunds, loyalty points, warranty periods, split shipments). Work through the policies step by step,
check each combination for conflicts, and output a final plan with the justification for each action."""

MESSAGE_SYSTEM = """Write the message to the customer explaining what we did and why. Be warm and plain-spoken;
if we could not fully resolve the issue, say so honestly and describe what happens next."""

ACCOUNT_SUMMARY_SYSTEM = "Summarize the following {kind} for a support agent in three bullet points."


def run_support_agent(ticket_text: str) -> str:
    messages = [{"role": "user", "content": ticket_text}]
    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=SUPPORT_SYSTEM,
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            return "".join(b.text for b in response.content if b.type == "text")
        results = []
        for block in response.content:
            if block.type == "tool_use":
                output = dispatch_tool(block.name, block.input)
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(output)})
        messages.append({"role": "user", "content": results})


def lookup_order_status(order_id: str) -> dict:
    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        tools=TOOLS[:3],
        tool_choice={"type": "tool", "name": "get_order"},
        messages=[{"role": "user", "content": f"Fetch order {order_id}"}],
    )
    call = next(b for b in response.content if b.type == "tool_use")
    return dispatch_tool(call.name, call.input)


def gather_account_context(customer_id: str) -> dict:
    orders = dispatch_tool("list_orders", {"id": customer_id})
    tickets = dispatch_tool("list_tickets", {"id": customer_id})
    invoices = dispatch_tool("list_invoices", {"id": customer_id})
    order_summary = client.messages.create(
        model=MODEL,
        max_tokens=300,
        system=ACCOUNT_SUMMARY_SYSTEM.format(kind="order history"),
        messages=[{"role": "user", "content": json.dumps(orders)}],
    )
    ticket_summary = client.messages.create(
        model=MODEL,
        max_tokens=300,
        system=ACCOUNT_SUMMARY_SYSTEM.format(kind="ticket history"),
        messages=[{"role": "user", "content": json.dumps(tickets)}],
    )
    invoice_summary = client.messages.create(
        model=MODEL,
        max_tokens=300,
        system=ACCOUNT_SUMMARY_SYSTEM.format(kind="invoices"),
        messages=[{"role": "user", "content": json.dumps(invoices)}],
    )
    return {
        "orders": order_summary.content[0].text,
        "tickets": ticket_summary.content[0].text,
        "invoices": invoice_summary.content[0].text,
    }


def plan_resolution(context: dict, issue: str) -> str:
    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        thinking={"type": "enabled", "budget_tokens": 4000},
        system=PLAN_SYSTEM,
        messages=[{"role": "user", "content": f"Issue: {issue}\n\nAccount context: {json.dumps(context)}"}],
    )
    return next(b.text for b in response.content if b.type == "text")


def compose_customer_message(plan: str, outcome: str) -> str:
    response = client.messages.create(
        model=MODEL,
        max_tokens=700,
        temperature=0.7,
        system=MESSAGE_SYSTEM,
        messages=[{"role": "user", "content": f"Plan:\n{plan}\n\nOutcome:\n{outcome}"}],
    )
    return response.content[0].text


def main(customer_id: str, issue: str) -> str:
    context = gather_account_context(customer_id)
    plan = plan_resolution(context, issue)
    outcome = run_support_agent(f"{issue}\n\nApproved plan:\n{plan}")
    return compose_customer_message(plan, outcome)
