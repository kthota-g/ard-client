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
                        "identifier": "urn:ai:travel-planner:registry:main",
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


async def wait_until_healthy(url: str, name: str, timeout_sec: float = 15.0):
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


async def main():
    print("==========================================================")
    print("            STARTING STANDALONE TRAVEL SERVERS            ")
    print("==========================================================")

    # 1. Start Registry Server
    registry_server = start_registry_server(REGISTRY_PORT)
    print(f"[+] Registry Server started on http://127.0.0.1:{REGISTRY_PORT}")

    # 2. Spawn Currency MCP Server
    mcp_script = os.path.join(os.path.dirname(__file__), "currency_mcp.py")
    print(f"[*] Spawning Currency MCP Server on http://127.0.0.1:{MCP_PORT}...")
    mcp_log = open("mcp.log", "w")
    mcp_proc = await asyncio.create_subprocess_exec(
        sys.executable,
        mcp_script,
        env={**os.environ, "PORT": str(MCP_PORT)},
        stdout=mcp_log,
        stderr=mcp_log,
    )

    # 3. Spawn A2A Travel Advisor
    a2a_script = os.path.join(os.path.dirname(__file__), "travel_agent.py")
    print(f"[*] Spawning A2A Travel Advisor on http://127.0.0.1:{A2A_PORT}...")
    a2a_log = open("a2a.log", "w")
    a2a_proc = await asyncio.create_subprocess_exec(
        sys.executable,
        a2a_script,
        env={**os.environ, "PORT": str(A2A_PORT)},
        stdout=a2a_log,
        stderr=a2a_log,
    )

    try:
        # 4. Wait for servers to be healthy
        await wait_until_healthy(f"http://127.0.0.1:{MCP_PORT}/", "Currency MCP Server")
        await wait_until_healthy(
            f"http://127.0.0.1:{A2A_PORT}/.well-known/agent-card.json",
            "A2A Travel Advisor Server",
        )
        print("[+] All servers are healthy and running!")
        print(
            f"    - Catalog Manifest: http://127.0.0.1:{REGISTRY_PORT}/.well-known/ai-catalog.json"
        )
        print("    - Press CTRL+C to terminate all servers.")
        print("-" * 58)

        # Block until interrupted
        while True:
            await asyncio.sleep(3600)

    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        print("\n[*] Terminating servers and cleaning up...")
        registry_server.shutdown()
        registry_server.server_close()

        if mcp_proc.returncode is None:
            try:
                mcp_proc.terminate()
                await mcp_proc.wait()
            except Exception:
                pass
        if a2a_proc.returncode is None:
            try:
                a2a_proc.terminate()
                await a2a_proc.wait()
            except Exception:
                pass

        mcp_log.close()
        a2a_log.close()
        print("[+] Cleanup complete. Servers stopped.")


def run_main():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[+] Exited cleanly.")


if __name__ == "__main__":
    run_main()
