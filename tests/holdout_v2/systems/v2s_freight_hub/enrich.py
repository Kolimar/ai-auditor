import anthropic

client = anthropic.Anthropic()


def enrich_shipment(shipment: dict) -> dict:
    note = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=150,
        messages=[
            {
                "role": "user",
                "content": "Condense this driver's note into one sentence for the control tower: "
                + shipment["driver_note"],
            }
        ],
    ).content[0].text

    local_instr = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=250,
        messages=[
            {
                "role": "user",
                "content": f"Translate the delivery instructions into {shipment['dest_language']}: "
                + shipment["delivery_instructions"],
            }
        ],
    ).content[0].text

    eta_text = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=120,
        messages=[
            {
                "role": "user",
                "content": f"Write a friendly two-line ETA message for the consignee {shipment['consignee']}, "
                f"arrival expected {shipment['eta']}.",
            }
        ],
    ).content[0].text

    return {**shipment, "tower_note": note, "local_instructions": local_instr, "eta_message": eta_text}
