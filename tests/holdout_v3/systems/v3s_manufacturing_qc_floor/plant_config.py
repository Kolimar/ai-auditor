import os
from pathlib import Path

OPUS = os.getenv("QC_OPUS", "claude-opus-4-1")
SONNET = os.getenv("QC_SONNET", "claude-sonnet-4-5")
HAIKU = os.getenv("QC_HAIKU", "claude-haiku-4-5")

SOP_MANUAL = Path(os.getenv("QC_SOP_FILE", "docs/assembly_sop_full.txt")).read_text()
STATIONS = ["ST-10", "ST-20", "ST-30", "ST-40", "ST-50", "ST-60"]
LOG_FILE = os.getenv("QC_LOG_FILE", "logs/line3_nightly.log")

SPEC = {"bore_mm": (24.985, 25.015), "flatness_mm": (0.0, 0.04), "torque_nm": (48.0, 52.0)}
