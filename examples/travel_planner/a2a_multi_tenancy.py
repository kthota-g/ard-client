"""Multi-tenancy variant of servers.py.

Same mock ARD registry, but it advertises and spawns MORE A2A agents on their own
ports: the original Travel Advisor plus a Weather Poet and a Personal Poet (both
defined in a2a_multi_tenancy_new.py), alongside the Currency MCP server. Nothing
from the original example is removed.

Run:  uv run start-multitenancy        (Ctrl+C stops everything)
"""

import asyncio
import http.server
import json
import os
import re
import sys
import threading
from urllib.parse import urlparse

import httpx

# --- CONFIGURATION ---
REGISTRY_PORT = 8500
MCP_PORT = 8501
A2A_PORT = 8502
WEATHER_PORT = 8503
POET_PORT = 8504

MOCK_AGENTS_DB = [
    {
        "identifier": "urn:ai:travel-planner:agent:currency-exchanger",
        "displayName": "Forex FX Converter",
        "type": "application/mcp-server+json",
        "description": "Calculates foreign exchange currency rates and converts major world currencies.",
        "tags": ["finance", "currency", "exchange", "money", "forex"],
        "capabilities": ["currency_conversion", "exchange_rates"],
        "representativeQueries": [
            "USD to JPY conversion rate",
            "convert money",
            "currency converter",
            "exchange dollars to euros",
            "how much is 100 USD in EUR",
        ],
        "version": "1.1.0",
        "data": {
            "transport": "streamable-http",
            "url": f"http://127.0.0.1:{MCP_PORT}/mcp",
        },
    },
    {
        "identifier": "urn:ai:travel-planner:agent:travel-advisor",
        "displayName": "A2A Travel Advisor",
        "type": "application/a2a-agent-card+json",
        "description": "Premium travel advisor that plans flights and hotel bookings.",
        "tags": [
            "travel",
            "planner",
            "advisor",
            "itinerary",
            "trip",
            "flights",
            "hotels",
            "vacation",
        ],
        "capabilities": ["travel_planning", "itinerary_generation"],
        "representativeQueries": [
            "plan a trip to Tokyo",
            "itinerary for Paris",
            "book a holiday in Berlin",
            "find flights and hotels for Tokyo",
        ],
        "version": "1.0.0",
        "url": f"http://127.0.0.1:{A2A_PORT}/.well-known/agent-card.json",
    },
    {
        "identifier": "urn:ai:travel-planner:agent:weather-poet",
        "displayName": "Weather Poet",
        "type": "application/a2a-agent-card+json",
        "description": "Looks up the weather for a place and time, then writes a haiku about it.",
        "tags": ["weather", "forecast", "haiku", "sky", "climate"],
        "capabilities": ["weather_lookup", "haiku_generation"],
        "representativeQueries": [
            "what is the weather in Berlin",
            "weather forecast as a haiku",
            "today's weather and a haiku",
        ],
        "version": "1.0.0",
        "url": f"http://127.0.0.1:{WEATHER_PORT}/.well-known/agent-card.json",
    },
    {
        "identifier": "urn:ai:travel-planner:agent:personal-poet",
        "displayName": "Personal Poet",
        "type": "application/a2a-agent-card+json",
        "description": "Asks a few friendly questions and writes a happy, personal poem for you.",
        "tags": ["poem", "poet", "personal", "fun", "delight"],
        "capabilities": ["poem_generation"],
        "representativeQueries": [
            "write me a poem",
            "a poem about me",
            "make me a happy poem",
        ],
        "version": "1.0.0",
        "url": f"http://127.0.0.1:{POET_PORT}/.well-known/agent-card.json",
    },
]

REGISTRY_SOURCE = "urn:ai:travel-planner:registry:main"

# --- DISCOVERY / RANKING ---
# A tiny, dependency-free matcher. Real ARD registries use vector search; here we
# score by token overlap so natural queries (not just exact keywords) resolve to
# the right resource.

_STOPWORDS = frozenset(
    "a an and are as at be by for from how i in into is it me my need of on or "
    "please that the to want what with you your".split()
)


def _tokenize(text: str) -> set[str]:
    """Lowercase, split on non-alphanumerics, and drop stopwords."""
    return {
        tok
        for tok in re.split(r"[^a-z0-9]+", text.lower())
        if tok and tok not in _STOPWORDS
    }


def score_entry(query: str, entry: dict) -> float:
    """Score a catalog entry against a free-text query (0-100, higher is better)."""
    q_tokens = _tokenize(query)
    if not q_tokens:
        return 0.0

    keywords: set[str] = set()
    for field in ("tags", "capabilities", "representativeQueries"):
        for value in entry.get(field, []):
            keywords |= _tokenize(value)
    keywords |= _tokenize(entry.get("displayName", ""))
    desc_tokens = _tokenize(entry.get("description", ""))

    keyword_hits = q_tokens & keywords
    desc_hits = (q_tokens & desc_tokens) - keyword_hits
    score = 18.0 * len(keyword_hits) + 6.0 * len(desc_hits)

    # Boost by the closest representative example query (fraction of it covered).
    best_example = 0.0
    for example in entry.get("representativeQueries", []):
        ex_tokens = _tokenize(example)
        if ex_tokens:
            best_example = max(best_example, len(q_tokens & ex_tokens) / len(ex_tokens))
    score += 40.0 * best_example

    return min(score, 100.0)


def search_catalog(query: str, db: list | None = None, limit: int = 10) -> list:
    """Rank catalog entries for a query and return ARD search-result dicts."""
    catalog = MOCK_AGENTS_DB if db is None else db
    results = []
    for entry in catalog:
        score = score_entry(query, entry)
        if score <= 0.0:
            continue
        results.append(
            {
                "identifier": entry["identifier"],
                "displayName": entry["displayName"],
                "type": entry["type"],
                "description": entry["description"],
                "tags": entry["tags"],
                "capabilities": entry["capabilities"],
                "representativeQueries": entry["representativeQueries"],
                "version": entry["version"],
                "score": round(score, 1),
                "source": REGISTRY_SOURCE,
                "url": entry.get("url"),
                "data": entry.get("data"),
            }
        )
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:limit]


class MockRegistryHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress logging to keep output clean

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/.well-known/ai-catalog.json":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            host_header = self.headers.get(
                "Host", f"localhost:{self.server.server_port}"
            )
            manifest = {
                "specVersion": "1.0",
                "host": {
                    "displayName": "Global Travel Agent Consortium",
                    "identifier": "urn:ai:travel-planner:host:global-travel",
                },
                "entries": [
                    {
                        "identifier": REGISTRY_SOURCE,
                        "displayName": "Travel Registry Service",
                        "type": "application/ai-registry+json",
                        "url": f"http://{host_header}/api/v1",
                    }
                ],
            }
            self.wfile.write(json.dumps(manifest).encode())
            return
        self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/v1/search":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            req = json.loads(body)
            query_obj = req.get("query", {})
            query = (
                query_obj.get("text", "")
                if isinstance(query_obj, dict)
                else str(query_obj)
            )

            results = search_catalog(query)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"results": results}).encode())
            return
        self.send_error(404)


def start_registry_server(port: int) -> http.server.HTTPServer:
    server = http.server.HTTPServer(("127.0.0.1", port), MockRegistryHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


async def wait_until_healthy(url: str, name: str, timeout_sec: float = 20.0):
    async with httpx.AsyncClient() as http_client:
        steps = int(timeout_sec / 0.5)
        for _ in range(steps):
            try:
                resp = await http_client.get(url)
                if resp.status_code in (200, 404):
                    return
            except httpx.NetworkError:
                pass
            await asyncio.sleep(0.5)
        raise RuntimeError(f"{name} healthy check failed at {url}")


async def _spawn(script_name: str, port: int, extra_env: dict | None = None):
    """Spawn a server script as a subprocess on its own port. Returns (proc, log)."""
    script = os.path.join(os.path.dirname(__file__), script_name)
    log = open(f"{script_name}.{port}.log", "w")
    env = {**os.environ, "PORT": str(port)}
    if extra_env:
        env.update(extra_env)
    proc = await asyncio.create_subprocess_exec(
        sys.executable, script, env=env, stdout=log, stderr=log
    )
    return proc, log


async def main():
    print("==========================================================")
    print("        STARTING MULTI-TENANCY A2A + ARD SERVERS          ")
    print("==========================================================")

    # 1. Registry (in-process thread).
    registry_server = start_registry_server(REGISTRY_PORT)
    print(f"[+] Registry Server started on http://127.0.0.1:{REGISTRY_PORT}")

    # 2. Spawn the resource servers, each on its own port.
    spawned = []  # list of (name, proc, log)
    plan = [
        ("currency_mcp.py", MCP_PORT, None, f"http://127.0.0.1:{MCP_PORT}/"),
        (
            "travel_agent.py",
            A2A_PORT,
            None,
            f"http://127.0.0.1:{A2A_PORT}/.well-known/agent-card.json",
        ),
        (
            "a2a_multi_tenancy_new.py",
            WEATHER_PORT,
            {"AGENT": "weather_poet"},
            f"http://127.0.0.1:{WEATHER_PORT}/.well-known/agent-card.json",
        ),
        (
            "a2a_multi_tenancy_new.py",
            POET_PORT,
            {"AGENT": "personal_poet"},
            f"http://127.0.0.1:{POET_PORT}/.well-known/agent-card.json",
        ),
    ]
    health = []
    for script, port, extra_env, health_url in plan:
        label = (extra_env or {}).get("AGENT", script)
        print(f"[*] Spawning {label} on http://127.0.0.1:{port}...")
        proc, log = await _spawn(script, port, extra_env)
        spawned.append((label, proc, log))
        health.append((health_url, label))

    try:
        for url, name in health:
            await wait_until_healthy(url, name)
        print("[+] All servers are healthy and running!")
        print(
            f"    - Catalog Manifest: http://127.0.0.1:{REGISTRY_PORT}/.well-known/ai-catalog.json"
        )
        print("    - Press CTRL+C to terminate all servers.")
        print("-" * 58)

        while True:
            await asyncio.sleep(3600)

    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        print("\n[*] Terminating servers and cleaning up...")
        registry_server.shutdown()
        registry_server.server_close()
        for _label, proc, log in spawned:
            if proc.returncode is None:
                try:
                    proc.terminate()
                    await proc.wait()
                except Exception:
                    pass
            log.close()
        print("[+] Cleanup complete. Servers stopped.")


def run_main():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[+] Exited cleanly.")


if __name__ == "__main__":
    run_main()
