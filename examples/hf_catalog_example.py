import asyncio
from ard_client import fetch_manifest, ArdClient

async def main():
    # URL of the Hugging Face ARD capability manifest
    manifest_url = "https://evalstate-hf-agentfinder.hf.space/.well-known/ai-catalog.json"
    
    print(f"1. Fetching capability manifest from: {manifest_url}")
    manifest = await fetch_manifest(manifest_url)
    
    print(f"Catalog Host: {manifest.host.displayName} ({manifest.host.identifier})")
    
    # 2. Bootstrap ArdClient automatically from the manifest.
    # The SDK automatically finds the advertised registry entries, normalizes the URLs
    # (handling HTTP/HTTPS redirection and trailing endpoint suffixes), and configures the base URL.
    print("\n2. Initializing ArdClient from the manifest...")
    async with ArdClient.from_manifest(manifest) as client:
        print(f"Connected to registry at: {client.base_url}")
        
        # 3. Invoke semantic search on the dynamic registry
        query_text = "removing background from an image"
        print(f"\n3. Searching the dynamic registry for: '{query_text}'...")
        response = await client.search(
            text=query_text,
            page_size=5
        )
        
        import json
        print("\n4. Raw JSON Response:")
        print(json.dumps(response.to_dict(), indent=2))
        
        print(f"\nFound {len(response.results)} search results:")
        for idx, result in enumerate(response.results):
            print(f"- [{result.score:.2f}%] {result.displayName} ({result.type_})")
            print(f"  Identifier: {result.identifier}")
            if result.description:
                print(f"  Description: {result.description}")
            print()

if __name__ == "__main__":
    asyncio.run(main())
