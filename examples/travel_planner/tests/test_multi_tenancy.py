"""Tests for the multi-tenancy variant: expanded catalog routing + the new agents.

Registry/ranking runs in-process; the HTTP test starts the registry on an
ephemeral port and shuts it down. No model calls, no standalone servers.
"""

import httpx

import servers as mt
import a2a_multi_tenancy_new as agents


def test_catalog_has_four_resources():
    assert len(mt.MOCK_AGENTS_DB) == 4


def test_weather_query_routes_to_weather_poet():
    results = mt.search_catalog("what is the weather forecast today")
    assert results[0]["displayName"] == "Weather Poet"


def test_poem_query_routes_to_personal_poet():
    results = mt.search_catalog("write me a happy poem about myself")
    assert results[0]["displayName"] == "Personal Poet"


def test_existing_routing_still_works():
    assert (
        mt.search_catalog("plan a trip to Tokyo")[0]["displayName"]
        == "A2A Travel Advisor"
    )
    assert (
        mt.search_catalog("convert 100 USD to EUR")[0]["type"]
        == "application/mcp-server+json"
    )


def test_new_agents_build_and_have_expected_tools():
    assert set(agents.AGENTS) == {"weather_poet", "personal_poet"}
    # Weather Poet uses the built-in google_search tool; Personal Poet uses none.
    assert len(agents.weather_poet_agent.tools) == 1
    assert len(agents.personal_poet_agent.tools) == 0
    assert type(agents.build_app("weather_poet")).__name__ == "Starlette"
    assert type(agents.build_app("personal_poet")).__name__ == "Starlette"


def test_http_search_routes_weather_in_process():
    server = mt.start_registry_server(0)
    port = server.server_address[1]
    try:
        resp = httpx.post(
            f"http://127.0.0.1:{port}/api/v1/search",
            json={"query": {"text": "give me a haiku about the weather"}},
            timeout=5.0,
        )
        results = resp.json()["results"]
        assert results
        assert results[0]["displayName"] == "Weather Poet"
    finally:
        server.shutdown()
        server.server_close()
