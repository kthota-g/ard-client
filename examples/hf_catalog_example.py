import asyncio
from ard_client import ArdClient


async def main():
    
    print("1. Initializing ArdClient...")
    async with ArdClient("https://evalstate-hf-agentfinder.hf.space/") as client:
        print(f"Connected to registry at: {client.base_url}")

        # 2. Invoke semantic search on the dynamic registry
        query_text = "removing background from an image"
        print(f"\n2. Searching the dynamic registry for: '{query_text}'...")
        response = await client.search(text=query_text, page_size=5)

        import json

        print("\n3. Raw JSON Response:")
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
