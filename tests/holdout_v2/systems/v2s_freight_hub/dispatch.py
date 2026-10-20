from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

CERTIFIED_HAZMAT = {"Transportes Vela", "NordHaz", "Kaluga Cargo"}

llm = ChatAnthropic(model="claude-sonnet-4-5", temperature=0, max_tokens=50)

CARRIER_RULES = f"""Select the vehicle class and carrier pool for a shipment.
Rules, applied in this order:
1. hazmat is true -> carrier pool CERTIFIED ({', '.join(sorted(CERTIFIED_HAZMAT))}).
2. weight_kg greater than 20000 -> FLATBED.
3. distance_km under 300 -> LOCAL_VAN.
4. otherwise -> STANDARD_TRUCK.
Answer with the single resulting label."""


def pick_carrier(shipment: dict) -> str:
    human = (
        f"hazmat={shipment['hazmat']}\n"
        f"weight_kg={shipment['weight_kg']}\n"
        f"distance_km={shipment['distance_km']}"
    )
    out = llm.invoke([SystemMessage(content=CARRIER_RULES), HumanMessage(content=human)])
    return out.content.strip()


def plan_consolidation(shipments: list[dict], depot_constraints: str) -> str:
    big = ChatAnthropic(model="claude-opus-4-1", max_tokens=3000)
    listing = "\n".join(
        f"{s['id']}: {s['origin']}->{s['dest']} {s['weight_kg']}kg window {s['window']}" for s in shipments
    )
    msgs = [
        SystemMessage(
            content="You plan load consolidation for a freight forwarder. Group shipments that can "
            "share a vehicle without breaking delivery windows or depot constraints, and justify "
            "the trade-offs between extra stops and saved trips."
        ),
        HumanMessage(content=f"Constraints:\n{depot_constraints}\n\nShipments:\n{listing}"),
    ]
    return big.invoke(msgs).content
