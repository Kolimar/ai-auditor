import os

PRIMARY_MODEL = os.environ.get("BILLING_MODEL", "gpt-4o")
LIGHT_MODEL = os.environ.get("BILLING_LIGHT_MODEL", "gpt-4o-mini")
RESPONSES_MODEL = os.environ.get("BILLING_RESPONSES_MODEL", "gpt-4.1")

TIERS = [
    {"upto_kwh": 200, "rate": 0.11},
    {"upto_kwh": 600, "rate": 0.16},
    {"upto_kwh": None, "rate": 0.24},
]
