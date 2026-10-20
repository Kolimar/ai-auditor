from agents import Agent

from tools import hold_seat, search_flights, search_hotels

FLIGHT_INSTRUCTIONS = """You are the flights specialist for Meridian Travel.
Use search_flights to find options that fit the traveller's dates and budget, compare them
(stops, duration, baggage) and, once the traveller picks one, call hold_seat.
Prices must always be quoted in the currency the traveller used."""

FRONT_DESK_INSTRUCTIONS = (
    "Eres la recepción virtual. Cuando llegue una petición de vuelos, "
    "pásala al especialista de vuelos tal cual. No respondas tú."
)

WRITER_INSTRUCTIONS = """Eres redactor de itinerarios. Con el plan de vuelos y hoteles que te dan,
escribe un itinerario día a día en el idioma del cliente. Añade una o dos recomendaciones locales
por jornada (comida, paseos, horarios que conviene evitar) con un tono entusiasta pero realista."""

COMPLAINT_INSTRUCTIONS = """Atiendes reclamaciones de viajeros. Responde en español neutro,
reconoce el problema concreto que describe la persona, di qué vas a hacer y evita frases hechas.
No prometas compensaciones; eso lo decide el equipo humano."""

flights_specialist = Agent(
    name="FlightsSpecialist",
    instructions=FLIGHT_INSTRUCTIONS,
    model="gpt-4.1",
    tools=[search_flights, hold_seat],
)

hotels_specialist = Agent(
    name="HotelsSpecialist",
    instructions="Find hotels with search_hotels that fit the traveller's budget and neighbourhood wishes.",
    model="gpt-4.1",
    tools=[search_hotels],
)

front_desk = Agent(
    name="BookingFrontDesk",
    instructions=FRONT_DESK_INSTRUCTIONS,
    model="gpt-4.1",
    handoffs=[flights_specialist],
)

itinerary_writer = Agent(
    name="ItineraryWriter",
    instructions=WRITER_INSTRUCTIONS,
    model="gpt-4.1",
)

complaint_responder = Agent(
    name="ComplaintResponder",
    instructions=COMPLAINT_INSTRUCTIONS,
    model="gpt-4.1",
)
