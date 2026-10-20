from agents import function_tool


@function_tool
def search_flights(origin: str, destination: str, date: str) -> str:
    """Search the fare cache for flights."""
    return f"[stub] flights {origin}->{destination} on {date}"


@function_tool
def hold_seat(flight_id: str, passenger: str) -> str:
    """Place a 15 minute hold on a seat."""
    return f"[stub] hold {flight_id} for {passenger}"


@function_tool
def search_hotels(city: str, checkin: str, nights: int) -> str:
    return f"[stub] hotels in {city}"
