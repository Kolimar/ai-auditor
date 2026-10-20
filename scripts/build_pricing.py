"""Build the packaged pricing catalog from scripts/pricing-raw.yaml.

Deterministic transformation; no prices are invented. Anthropic rows without an
API id get an id derived from the display name and are flagged ``id_derived``.
"""
import re
import sys
from pathlib import Path

import yaml

root = Path(__file__).resolve().parents[1]
raw = yaml.safe_load((root / "scripts/pricing-raw.yaml").read_text())
out = {
    "retrieved_at": raw["retrieved_at"],
    "verification": (
        "Extracted from official pricing pages through a summarizing fetch; Anthropic rows "
        "cross-checked against a second official page. Verify before relying on absolute numbers."
    ),
    "unit": "USD per 1M tokens",
    "models": [],
}
seen = set()
for prov in raw["providers"]:
    for m in prov["models"]:
        mid, derived = m.get("model"), False
        name = m.get("display_name") or ""
        if mid is None and prov["provider"] == "anthropic":
            base = re.sub(r"\(.*?\)", "", name).strip().lower()
            mid, derived = re.sub(r"[ .]+", "-", base), True
        if mid is None:
            continue
        cond = None
        if "over 100,000" in name:
            cond = "prompt_tokens > 100000"
        elif "up to 100,000" in name:
            cond = "prompt_tokens <= 100000"
        key = (mid, cond)
        if key in seen:
            continue
        seen.add(key)
        entry = {
            "id": mid,
            "provider": prov["provider"],
            "display_name": name,
            "input": m.get("input_per_mtok"),
            "output": m.get("output_per_mtok"),
            "cache_read": m.get("cache_read_per_mtok"),
            "cache_write": m.get("cache_write_per_mtok"),
            "batch_input": m.get("batch_input_per_mtok"),
            "batch_output": m.get("batch_output_per_mtok"),
            "source_url": prov["source_url"],
        }
        if cond:
            entry["condition"] = cond
        if derived:
            entry["id_derived"] = True
        if m.get("long_context_note"):
            entry["note"] = m["long_context_note"]
        out["models"].append(entry)
dest = root / "src/ai_auditor/cost/data/pricing.yaml"
dest.write_text(yaml.safe_dump(out, sort_keys=False, allow_unicode=True))
print(f"wrote {len(out['models'])} models to {dest}", file=sys.stderr)
