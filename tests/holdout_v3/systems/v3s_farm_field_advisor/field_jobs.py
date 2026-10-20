import json
from pathlib import Path

from google import genai
from google.genai import types

from knowledge import _store
from settings import GEMINI_FLASH, GEMINI_PRO

client = genai.Client()


def read_sensor_payload(payload_path: str) -> dict:
    raw = Path(payload_path).read_text()
    response = client.models.generate_content(
        model=GEMINI_FLASH,
        contents=(
            "The gateway posted the JSON document below. Report the soil moisture percentage, "
            "soil pH and battery voltage as a flat JSON object with keys moisture_pct, ph and "
            "battery_v.\n\n" + raw
        ),
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return json.loads(response.text)


def compute_irrigation_volume(area_ha: float, et0_mm: float, kc: float, efficiency: float) -> float:
    response = client.models.generate_content(
        model=GEMINI_PRO,
        contents=(
            f"Parcel area: {area_ha} ha. Reference evapotranspiration today: {et0_mm} mm. "
            f"Crop coefficient: {kc}. Irrigation system efficiency: {efficiency}. "
            "Net requirement in mm is et0 * kc, and 1 mm over 1 ha is 10 cubic metres. "
            "How many cubic metres should be applied today? Answer with a single number."
        ),
    )
    return float(response.text.strip())


def write_field_brief(fields: list[dict]) -> list[str]:
    briefs = []
    store = _store("extension_bulletins")
    for field in fields:
        guidance = store.similarity_search("standard drip irrigation guidance for mature trees", k=4)
        notes = "\n".join(d.page_content for d in guidance)
        response = client.models.generate_content(
            model=GEMINI_FLASH,
            contents=(
                f"Field {field['name']} ({field['crop']}), last scouting remark: {field['remark']}.\n"
                f"Reference guidance:\n{notes}\n"
                "Write a three-sentence brief for the crew lead."
            ),
        )
        briefs.append(response.text)
    return briefs


def diagnose_leaf_photo(image_bytes: bytes, crop: str, notes: str) -> str:
    response = client.models.generate_content(
        model=GEMINI_PRO,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            f"This is a {crop} leaf photographed this morning. Scout notes: {notes}. "
            "List the most likely causes (pest, disease, nutrient, water stress) with what visual "
            "evidence supports each and what to confirm on site.",
        ],
    )
    return response.text


def plan_harvest_window(blocks: list[dict], forecast: str, crew_size: int, constraints: str) -> str:
    listing = "\n".join(
        f"{b['id']}: {b['variety']}, brix {b['brix']}, {b['hectares']} ha, picking cost class {b['cost_class']}"
        for b in blocks
    )
    response = client.models.generate_content(
        model=GEMINI_PRO,
        contents=(
            f"Blocks:\n{listing}\n\nForecast:\n{forecast}\n\nCrew available: {crew_size} people.\n"
            f"Constraints: {constraints}\n\n"
            "Propose an order and dates for harvesting the blocks, reasoning about ripeness, "
            "rain risk and crew capacity, and flag the trade-offs you made."
        ),
    )
    return response.text


def translate_advisory(text: str, language: str) -> str:
    response = client.models.generate_content(
        model=GEMINI_FLASH,
        contents=f"Translate this farm advisory into {language}, keeping product names and units unchanged:\n\n{text}",
    )
    return response.text
