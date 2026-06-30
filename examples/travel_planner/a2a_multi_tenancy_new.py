"""Extra A2A agents for the multi-tenancy demo: a Weather Poet and a Personal Poet.

Each is a Google ADK agent (gemini-3.5-flash) exposed over A2A. One file hosts
several agents; pick which one to serve with the AGENT env var (a2a_multi_tenancy.py
spawns each on its own port). Importing this module only builds the agent objects;
it never starts a server.
"""

import os

import uvicorn
from google.adk import Agent
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.tools import google_search

# 3.1 Weather Poet: asks where + when, looks up the weather, then writes a haiku.
# Only the built-in google_search tool is attached (ADK built-in tools are not
# mixed with custom function tools).
weather_poet_agent = Agent(
    name="weather_poet",
    model="gemini-3.5-flash",
    tools=[google_search],
    instruction=(
        "You are the Weather Poet. In your FIRST reply, greet briefly and ask the"
        " user two things: which location, and for which date or time. Once you have"
        " both, use google_search to find the weather for that place and time. Then"
        " reply in two parts: first a few clear lines of the actual weather details"
        " (temperature, conditions, wind if relevant); then a blank line followed by"
        " a single delightful haiku (three lines, 5-7-5 feel) inspired by that"
        " weather and place. Keep it warm and concise."
    ),
)

# 3.2 Personal Poet: asks a few friendly questions, then writes a happy poem.
personal_poet_agent = Agent(
    name="personal_poet",
    model="gemini-3.5-flash",
    instruction=(
        "You are the Personal Poet. Ask the user, ONE at a time across turns, four"
        " short questions: what shall I call you?, your favorite food?, your favorite"
        " color?, and a place you love. After you have all four answers, write a"
        " short original poem (4-8 lines) celebrating the person and their interests."
        " The poem must be positive, happy, and delightful. Do not ask anything else"
        " once you have the four answers."
    ),
)

AGENTS = {
    "weather_poet": weather_poet_agent,
    "personal_poet": personal_poet_agent,
}


def build_app(agent_key: str, host: str = "127.0.0.1", port: int = 8080):
    """Build the A2A Starlette app for one agent (does not start a server)."""
    if agent_key not in AGENTS:
        raise KeyError(f"Unknown agent {agent_key!r}; choose one of {list(AGENTS)}")
    return to_a2a(AGENTS[agent_key], host=host, port=port)


if __name__ == "__main__":
    agent_key = os.environ.get("AGENT", "weather_poet")
    port = int(os.environ.get("PORT", "8503"))
    app = build_app(agent_key, port=port)
    print(f"[*] Starting A2A agent '{agent_key}' on http://127.0.0.1:{port}...")
    uvicorn.run(app, host="127.0.0.1", port=port)
