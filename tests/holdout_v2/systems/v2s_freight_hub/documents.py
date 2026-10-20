import json

import anthropic

client = anthropic.Anthropic()

LIGHT = "claude-haiku-4-5"
MAIN = "claude-sonnet-4-5"


async def parse_edi_manifest(xml_body: str) -> dict:
    """Carriers send a fixed-schema XML manifest: <Manifest><Shipment id=..><Consignee>...</Consignee>
    <Weight unit="kg">...</Weight><PieceCount>...</PieceCount></Shipment></Manifest>"""
    aclient = anthropic.AsyncAnthropic()
    resp = await aclient.messages.create(
        model=LIGHT,
        max_tokens=600,
        messages=[
            {
                "role": "user",
                "content": "From this XML manifest give me shipment id, consignee name, weight in kg and "
                "piece count as JSON.\n" + xml_body,
            }
        ],
    )
    return json.loads(resp.content[0].text)


def customs_description_review(goods_description: str, hs_code: str, destination: str) -> str:
    resp = client.messages.create(
        model=MAIN,
        max_tokens=500,
        system=(
            "You help a customs broker. Decide whether the plain-language goods description is "
            "consistent with the declared HS code for the destination country and flag wording "
            "that could trigger an inspection."
        ),
        messages=[
            {
                "role": "user",
                "content": f"Destination: {destination}\nHS code: {hs_code}\nDescription: {goods_description}",
            }
        ],
    )
    return resp.content[0].text


def draft_delay_apology(customer: str, order_ref: str, reason_notes: str, new_eta: str) -> str:
    resp = client.messages.create(
        model=MAIN,
        max_tokens=400,
        temperature=0.7,
        system="Write a courteous, sincere email apologising for a delivery delay. Own the problem, "
        "explain the cause in plain words, give the new ETA and what we will do to make up for it.",
        messages=[
            {
                "role": "user",
                "content": f"Customer: {customer}\nOrder: {order_ref}\nWhat happened: {reason_notes}\nNew ETA: {new_eta}",
            }
        ],
    )
    return resp.content[0].text
