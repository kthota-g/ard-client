# Agent Finder Client

Python client library for consuming the Agent Finder Specification (federated discovery and search for agents).

## Features
- **Static Discovery**: Easily parse and validate capability manifests (`ai-catalog.json`) conforming to the standard schema.
- **Dynamic Search**: Seamless asynchronous client for semantically searching dynamically federated Agent Registries.
- **Facet Introspection**: Run aggregated bucket queries on the dynamic `/explore` endpoint.
- **Error Handling**: Robust wrapping of all HTTP-status and network exceptions under a cohesive, clean exception tree.
- **Customizable client**: Easily configure authorization headers, timeouts, proxy transports, and reuse existing HTTP client instances.

## Installation
Requires Python >= 3.13. 

```bash
uv add agent-finder-client
```

---

## Usage Examples

### 1. Static Manifest Discovery
Retrieve and parse a static capability manifest hosted at the well-known URI of a domain.

```python
import asyncio
from agent_finder_client import fetch_manifest

async def main():
    # Automatically queries "https://example.com/.well-known/ai-catalog.json"
    manifest = await fetch_manifest("example.com")
    
    print(f"Catalog Host: {manifest.host.displayName}")
    for entry in manifest.entries:
        print(f"- {entry.displayName} ({entry.identifier})")
        print(f"  Type: {entry.type_}")
        if entry.url:
            print(f"  Reference URL: {entry.url}")

asyncio.run(main())
```

### 2. Initialize Client from Manifest
Bootstrap the Agent Finder client dynamically by searching a capability manifest for advertised registries.

```python
import asyncio
from agent_finder_client import fetch_manifest, AgentFinderClient

async def main():
    manifest = await fetch_manifest("example.com")
    
    # Automatically discovers registry entries and configures base_url
    async with AgentFinderClient.from_manifest(manifest) as client:
        print(f"Connected to dynamic registry at: {client.base_url}")
        # Execute searches or exploration...

asyncio.run(main())
```

### 3. Dynamic Semantic Search
Perform natural language semantic searches against a dynamic Agent Registry.

```python
import asyncio
from agent_finder_client import AgentFinderClient

async def main():
    async with AgentFinderClient(base_url="https://registry.example.com/api/v1") as client:
        response = await client.search(
            text="find me a flight booking agent",
            filter_={
                "type": ["application/a2a-agent-card+json"],
                "trustManifest.attestations.type": ["SOC2-Type2"]
            },
            federation="referrals",
            page_size=5
        )
        
        print(f"Found {len(response.results)} results:")
        for result in response.results:
            print(f"- [{result.score}%] {result.displayName} (Source: {result.source})")
            print(f"  URN: {result.identifier}")
            
        if response.referrals:
            print(f"\nRecommended upstream registries (referrals):")
            for ref in response.referrals:
                print(f"- {ref.displayName} -> {ref.url} ({ref.type_})")

asyncio.run(main())
```

### 4. Registry Introspection (Facets & Explore)
Execute aggregated statistical and bucket queries over matched capabilities in the search registry.

```python
import asyncio
from agent_finder_client import (
    AgentFinderClient,
    ExploreResultType,
    ExploreFacetRequest
)

async def main():
    async with AgentFinderClient(base_url="https://registry.example.com/api/v1") as client:
        # Setup aggregation fields for facet breakdowns
        result_type = ExploreResultType(
            facets=[
                ExploreFacetRequest(field="type", limit=10),
                ExploreFacetRequest(field="publisher", limit=5)
            ]
        )
        
        response = await client.explore(
            result_type=result_type,
            text="currency conversion"
        )
        
        for field, facet_result in response.facets.items():
            print(f"\nFacet breakdown for '{field}':")
            for bucket in facet_result.buckets:
                print(f"- {bucket.value}: {bucket.count} matches")
            if facet_result.otherCount:
                print(f"- Other buckets count: {facet_result.otherCount}")

asyncio.run(main())
```

### 5. Browsing Deterministically
Query the dynamic registry deterministically using structured filter syntax (ideal for developer portals).

```python
import asyncio
from agent_finder_client import AgentFinderClient

async def main():
    async with AgentFinderClient(base_url="https://registry.example.com/api/v1") as client:
        response = await client.list_agents(
            filter_expr="type = 'application/mcp-server+json' AND createdAfter > '2026-01-01'",
            order_by="displayName ASC",
            page_size=20
        )
        
        for entry in response.items:
            print(f"- {entry.displayName} [{entry.type_}] ({entry.identifier})")

asyncio.run(main())
```