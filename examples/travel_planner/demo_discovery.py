"""Non-interactive ARD discovery walkthrough — no model, no standalone servers.

Starts the mock ARD registry in-process and uses the ard-client SDK to discover
the right resource for each example query, printing the discover -> route flow.
Handy as a fast sanity check and to record the discovery half of the live demo.

Run:  uv run demo          (or)   uv run python demo_discovery.py
"""

import asyncio

from ard_client import ArdClient, fetch_manifest

import servers

QUERIES = [
    "plan a trip to Tokyo",
    "convert 100 USD to EUR",
    "what is the weather forecast and a haiku",
    "write me a happy poem about me",
    "tell me a dad joke",  # intentionally has no matching resource
]

# How each catalog entry type would be invoked after discovery.
PROTOCOL_BY_TYPE = {
    "application/a2a-agent-card+json": "A2A (multi-turn agent chat)",
    "application/mcp-server+json": "MCP (tool call)",
    "application/mcp-server-card+json": "MCP (tool call)",
}


async def _run():
    # Registry runs in-process on an ephemeral port; always torn down below.
    server = servers.start_registry_server(0)
    port = server.server_address[1]
    well_known = f"http://127.0.0.1:{port}/.well-known/ai-catalog.json"
    try:
        manifest = await fetch_manifest(well_known)
        async with ArdClient.from_manifest(manifest) as client:
            print(f"Connected to ARD registry: {manifest.host.displayName}\n")
            for query in QUERIES:
                res = await client.search(text=query)
                if not res.results:
                    print(f"  -  {query!r:42}  ->  (no matching resource)")
                    continue
                top = res.results[0]
                route = PROTOCOL_BY_TYPE.get(top.type_, top.type_)
                print(
                    f"  >  {query!r:42}  ->  {top.displayName}  (score {top.score:.0f})"
                )
                print(f"       then invoke over {route}")
    finally:
        server.shutdown()
        server.server_close()


def main():
    asyncio.run(_run())


if __name__ == "__main__":
    main()
