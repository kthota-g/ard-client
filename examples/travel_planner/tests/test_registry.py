"""Tests for the travel_planner mock ARD registry: ranking + HTTP endpoints.

All tests run in-process. The HTTP test starts the registry on an ephemeral port
in a background thread and shuts it down again, so nothing blocks.
"""

import httpx

import servers


def test_currency_query_ranks_currency_first():
    results = servers.search_catalog("convert 100 USD to EUR")
    assert results
    assert results[0]["type"] == "application/mcp-server+json"


def test_travel_query_ranks_travel_first():
    results = servers.search_catalog("plan a trip to Tokyo")
    assert results
    assert results[0]["type"] == "application/a2a-agent-card+json"


def test_natural_language_generalizes_beyond_seeded_queries():
    # Phrasing matches no representative query verbatim; it resolves via the
    # "vacation" tag alone, proving the matcher generalizes.
    results = servers.search_catalog("any good vacation ideas")
    assert results
    assert results[0]["displayName"] == "A2A Travel Advisor"


def test_unrelated_query_returns_nothing():
    assert servers.search_catalog("tell me a dad joke") == []


def test_empty_query_scores_zero():
    assert servers.score_entry("", servers.MOCK_AGENTS_DB[0]) == 0.0


def test_scores_are_bounded_and_sorted():
    results = servers.search_catalog("currency converter exchange money")
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)
    assert all(0.0 < s <= 100.0 for s in scores)


def test_http_manifest_and_search_in_process():
    server = servers.start_registry_server(0)  # port 0 -> ephemeral
    port = server.server_address[1]
    try:
        base = f"http://127.0.0.1:{port}"
        manifest = httpx.get(f"{base}/.well-known/ai-catalog.json", timeout=5.0).json()
        assert manifest["specVersion"] == "1.0"
        assert manifest["entries"][0]["type"] == "application/ai-registry+json"

        resp = httpx.post(
            f"{base}/api/v1/search",
            json={"query": {"text": "plan a trip to Tokyo"}},
            timeout=5.0,
        )
        results = resp.json()["results"]
        assert results
        assert results[0]["displayName"] == "A2A Travel Advisor"
    finally:
        server.shutdown()
        server.server_close()
