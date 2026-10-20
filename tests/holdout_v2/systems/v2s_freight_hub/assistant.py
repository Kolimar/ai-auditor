import anthropic

client = anthropic.Anthropic()


def _tool(name: str, description: str, **props: str) -> dict:
    return {
        "name": name,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": {k: {"type": v} for k, v in props.items()},
            "required": list(props),
        },
    }


DISPATCH_TOOLS = [
    _tool("get_shipment_status", "Current status of a shipment.", shipment_id="string"),
    _tool("get_driver_location", "Last GPS ping of the assigned driver.", shipment_id="string"),
    _tool("reassign_driver", "Assign a different driver to a shipment.", shipment_id="string", driver_id="string"),
    _tool("cancel_shipment", "Cancel a shipment and release the capacity.", shipment_id="string"),
    _tool("create_pickup_order", "Create a new pickup order.", origin="string", dest="string"),
    _tool("update_customs_docs", "Attach or replace customs documents.", shipment_id="string", doc_url="string"),
    _tool("quote_spot_rate", "Spot rate for a lane.", origin="string", dest="string"),
    _tool("list_depot_inventory", "Stock held at a depot.", depot_id="string"),
    _tool("schedule_dock_slot", "Book a dock slot at a depot.", depot_id="string", slot="string"),
    _tool("refund_customer", "Issue a refund for an order.", order_ref="string", amount="string"),
    _tool("block_carrier", "Add a carrier to the blocklist.", carrier_id="string"),
    _tool("export_manifest_pdf", "Render the manifest as PDF.", shipment_id="string"),
]


def answer_status_question(question: str) -> str:
    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=400,
        system=(
            "You answer customers' questions about where their shipment is. Look up the "
            "shipment status or the driver location and answer in one or two sentences."
        ),
        tools=DISPATCH_TOOLS,
        messages=[{"role": "user", "content": question}],
    )
    return resp.content[-1].text


TARIFF_MANUAL = open("data/tariff_manual_2026.txt", encoding="utf-8").read()


def answer_tariff_question(question: str) -> str:
    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=500,
        temperature=0,
        system="You answer questions for sales reps using the tariff manual below.\n\n" + TARIFF_MANUAL,
        messages=[{"role": "user", "content": question}],
    )
    return resp.content[0].text


def triage_tariff_inbox(questions: list[str]) -> list[str]:
    return [answer_tariff_question(q) for q in questions]
