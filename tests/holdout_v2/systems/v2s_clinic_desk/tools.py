from agents import function_tool


@function_tool
def lookup_patient(phone: str) -> dict:
    """Find a patient record by phone number."""
    return {"phone": phone, "id": "P-1042", "plan": "BlueLine PPO"}


@function_tool
def check_coverage(patient_id: str, service_code: str) -> dict:
    """Ask the insurer gateway whether the service is covered."""
    return {"covered": True, "deductible_left": 120.0}


@function_tool
def get_copay(patient_id: str, service_code: str) -> float:
    """Return the copay the patient owes for the service."""
    return 25.0


@function_tool
def find_slots(provider: str, week_of: str) -> list[str]:
    """List open appointment slots for a provider."""
    return ["2026-11-03T09:00", "2026-11-03T14:30"]


@function_tool
def book_slot(patient_id: str, slot: str) -> str:
    """Book the appointment and return a confirmation code."""
    return "CONF-8841"


@function_tool
def list_open_invoices(patient_id: str) -> list[dict]:
    """Return unpaid invoices for the patient."""
    return []
