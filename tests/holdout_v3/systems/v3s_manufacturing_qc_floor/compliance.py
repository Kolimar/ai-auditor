import anthropic

from plant_config import SONNET, SOP_MANUAL, STATIONS
from prompts import COMPLIANCE_PROMPT

client = anthropic.Anthropic()


def check_station_compliance(reports: dict[str, str]) -> dict[str, str]:
    verdicts = {}
    for station in STATIONS:
        msg = client.messages.create(
            model=SONNET,
            max_tokens=600,
            system=COMPLIANCE_PROMPT + "\n\n=== SOP ===\n" + SOP_MANUAL,
            messages=[{"role": "user", "content": f"Station {station}: {reports[station]}"}],
        )
        verdicts[station] = msg.content[0].text
    return verdicts
