"""Tests for the ADK travel agent's tools and A2A wiring (no model calls)."""

import travel_agent


def test_search_flights_mentions_destination_and_date():
    out = travel_agent.search_flights("Tokyo", "2026-07-01")
    assert "TOKYO" in out
    assert "2026-07-01" in out


def test_search_hotels_mentions_destination_and_dates():
    out = travel_agent.search_hotels("Tokyo", "2026-07-01", "2026-07-05")
    assert "Tokyo" in out
    assert "2026-07-01" in out and "2026-07-05" in out


def test_agent_has_two_tools_and_name():
    assert travel_agent.travel_agent.name == "travel_agent"
    assert len(travel_agent.travel_agent.tools) == 2


def test_agent_is_exposed_as_a2a_app():
    # to_a2a() builds a Starlette app object; it does not start a server.
    assert type(travel_agent.app).__name__ == "Starlette"
