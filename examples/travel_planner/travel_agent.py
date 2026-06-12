import os
import uvicorn

from google.adk import Agent
from google.adk.a2a.utils.agent_to_a2a import to_a2a

# --- TRAVEL PLANNING FUNCTION TOOLS ---


def search_flights(destination: str, departure_date: str) -> str:
    """Search for flight options to the given destination.

    Args:
        destination: Destination city or airport code (e.g. Tokyo, TYO).
        departure_date: Departure date in YYYY-MM-DD format.
    """
    dest = destination.upper()
    return (
        f"Available Flights to {dest} on {departure_date}:\n"
        f"1. SkyExpress #281 - NYC to {dest} - Dep: 10:00 AM - Price: $850 (Economy)\n"
        f"2. PacificAir #902 - NYC to {dest} - Dep: 02:30 PM - Price: $1200 (Premium Economy)\n"
        f"3. NipponFly #44 - NYC to {dest} - Dep: 06:15 PM - Price: $3100 (Business Class)"
    )


def search_hotels(destination: str, checkin_date: str, checkout_date: str) -> str:
    """Search for lodging accommodations in the destination city.

    Args:
        destination: Destination city or neighborhood (e.g. Shinjuku, Tokyo).
        checkin_date: Check-in date in YYYY-MM-DD.
        checkout_date: Check-out date in YYYY-MM-DD.
    """
    dest = destination.title()
    return (
        f"Top Lodging Options in {dest} from {checkin_date} to {checkout_date}:\n"
        f"1. Shinjuku Grand Stay (Hotel) - Location: Central - Price: $180/night (Rating: 4.8/5)\n"
        f"2. Yoyogi Quiet Villa (Boutique) - Location: Residential - Price: $220/night (Rating: 4.9/5)\n"
        f"3. Tokyo Capsule Lodge (Budget) - Location: Near Station - Price: $45/night (Rating: 4.2/5)"
    )


# --- AGENT AND SERVER INITIALIZATION ---

# Define the Google ADK Agent
travel_agent = Agent(
    name="travel_agent",
    model="gemini-3.5-flash",
    instruction=(
        "You are a premium travel coordinator agent. Help users plan their travel itinerary "
        "by searching for flights and hotels, and summarizing them clearly to present a beautiful synthesized travel report."
    ),
    tools=[search_flights, search_hotels],
)

port_env = int(os.environ.get("PORT", "8080"))

# Convert the ADK Agent to an A2A Starlette app
app = to_a2a(
    agent=travel_agent,
    host="127.0.0.1",
    port=port_env,
)

if __name__ == "__main__":
    print(f"[*] Starting A2A Travel Agent Server on http://127.0.0.1:{port_env}...")
    uvicorn.run(app, host="127.0.0.1", port=port_env)
