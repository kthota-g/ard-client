"""End-to-end discovery via the real ard-client SDK against the in-process registry.

Starts the registry on an ephemeral port, runs the SDK's fetch_manifest +
search, then shuts the registry down. No model calls, nothing left running.
"""

import asyncio

from ard_client import ArdClient, fetch_manifest

import servers


def _discover(query: str):
    server = servers.start_registry_server(0)
    port = server.server_address[1]
    well_known = f"http://127.0.0.1:{port}/.well-known/ai-catalog.json"

    async def run():
        manifest = await fetch_manifest(well_known)
        async with ArdClient.from_manifest(manifest) as client:
            return await client.search(text=query)

    try:
        return asyncio.run(run())
    finally:
        server.shutdown()
        server.server_close()


def test_sdk_resolves_travel_query_to_a2a_agent():
    res = _discover("plan a trip to Tokyo")
    assert res.results
    assert res.results[0].type_ == "application/a2a-agent-card+json"
    assert res.results[0].url  # A2A entries carry a card URL


def test_sdk_resolves_currency_query_to_mcp_server():
    res = _discover("convert 100 USD to EUR")
    assert res.results
    assert res.results[0].type_ == "application/mcp-server+json"
