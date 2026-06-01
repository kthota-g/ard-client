import asyncio
import sys
import uuid
from urllib.parse import urlparse

import httpx
from a2a.client.client import ClientConfig as A2AClientConfig
from a2a.client.client_factory import ClientFactory as A2AClientFactory
from a2a.client.card_resolver import A2ACardResolver
from a2a.types import Message as A2AMessage, Part as A2APart
from a2a.types import TransportProtocol as A2ATransport
from google.adk.tools.mcp_tool.mcp_session_manager import (
    MCPSessionManager,
    StreamableHTTPConnectionParams,
)
from rich.console import Console
from rich.panel import Panel

from ard_client import ArdClient, fetch_manifest

ALLOWED_REGISTRIES = [
    "http://127.0.0.1:8500/.well-known/ai-catalog.json",
]

console = Console()


def print_a2a_response(response) -> str | None:
    """Helper to parse and print text content from any standard A2A response payload.

    Returns:
        The context_id returned by the server, if any.
    """
    context_id = None
    if isinstance(response, A2AMessage):
        context_id = response.context_id
        for part in response.parts:
            if hasattr(part, "text") and part.text:
                console.print(part.text, end="", highlight=False)
    elif isinstance(response, tuple):
        task, update = response
        if task:
            context_id = task.context_id
        if update is not None:
            if hasattr(update, "status") and update.status and update.status.message:
                for part in update.status.message.parts:
                    if hasattr(part, "text") and part.text:
                        console.print(part.text, end="", highlight=False)
                    elif (
                        hasattr(part, "root")
                        and hasattr(part.root, "text")
                        and part.root.text
                    ):
                        console.print(part.root.text, end="", highlight=False)
        else:
            if task and task.status and task.status.message:
                for part in task.status.message.parts:
                    if hasattr(part, "text") and part.text:
                        console.print(part.text, end="", highlight=False)
                    elif (
                        hasattr(part, "root")
                        and hasattr(part.root, "text")
                        and part.root.text
                    ):
                        console.print(part.root.text, end="", highlight=False)
            if task and task.artifacts:
                for artifact in task.artifacts:
                    if artifact.parts:
                        for part in artifact.parts:
                            if hasattr(part, "text") and part.text:
                                console.print(part.text, end="", highlight=False)
                            elif (
                                hasattr(part, "root")
                                and hasattr(part.root, "text")
                                and part.root.text
                            ):
                                console.print(part.root.text, end="", highlight=False)
    return context_id


async def handle_mcp_server(entry, query: str):
    """Interactively inspect tools on a discovered MCP server and execute a selected tool."""
    url = entry.data.get("url")
    console.print(
        f"[bold magenta]🔌[/] [magenta]Instantiating MCP Client for: [bold]{entry.displayName}[/] ({url})...[/]"
    )
    manager = MCPSessionManager(
        connection_params=StreamableHTTPConnectionParams(url=url)
    )
    try:
        session = await manager.create_session()

        # 1. Fetch available tools
        tools_result = await session.list_tools()
        tools = tools_result.tools
        if not tools:
            console.print("[bold red]❌ No tools found on this MCP server.[/]")
            return

        console.print("\n[bold cyan]🔧 Available Tools:[/]")
        for idx, tool in enumerate(tools):
            desc = (
                tool.description.split("\n\n")[0].split("Args:")[0].strip()
                if tool.description
                else ""
            )
            console.print(f"  [bold cyan][{idx + 1}][/] [bold]{tool.name}[/]: {desc}")

        # 2. Let user choose a tool
        choice = console.input(
            f"\n[bold yellow]Select tool to invoke (1-{len(tools)}): [/]"
        ).strip()
        try:
            choice_idx = int(choice) - 1
            if choice_idx < 0 or choice_idx >= len(tools):
                raise ValueError()
        except ValueError:
            console.print("[bold red]❌ Invalid selection.[/]")
            return

        selected_tool = tools[choice_idx]
        console.print(
            f"\n[bold green]✅ Selected Tool:[/] [bold]{selected_tool.name}[/]"
        )

        # 3. Query parameters dynamically
        arguments = {}
        schema = selected_tool.inputSchema or {}
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        if properties:
            console.print(
                "\n[bold yellow]✍️  Please provide values for the arguments:[/]"
            )
            for prop_name, prop_info in properties.items():
                req_marker = " [bold red](Required)[/]" if prop_name in required else ""
                val = console.input(
                    f"  - [bold]{prop_name}[/] ({prop_info.get('type', 'any')}){req_marker}: "
                ).strip()
                if val:
                    # Basic casting
                    prop_type = prop_info.get("type")
                    if prop_type == "number":
                        arguments[prop_name] = float(val)
                    elif prop_type == "integer":
                        arguments[prop_name] = int(val)
                    elif prop_type == "boolean":
                        arguments[prop_name] = val.lower() in (
                            "true",
                            "1",
                            "yes",
                        )
                    else:
                        arguments[prop_name] = val
                elif prop_name in required:
                    console.print(
                        f"[bold red]⚠️  Warning: Missing required argument: {prop_name}[/]"
                    )

        # 4. Invoke
        console.print(
            f"\n[bold cyan]⚡[/] [cyan]Invoking tool [bold]{selected_tool.name}[/] with arguments: {arguments}...[/]"
        )
        result = await session.call_tool(name=selected_tool.name, arguments=arguments)

        console.print("\n[bold green]✨ Result:[/]")
        for content in result.content:
            if hasattr(content, "text"):
                console.print(content.text, highlight=False)
            elif isinstance(content, dict) and "text" in content:
                console.print(content["text"], highlight=False)
            else:
                console.print(content, highlight=False)

    finally:
        await manager.close()


async def handle_a2a_server(entry, query: str):
    """Instantiate standard A2A client, send user query as request, and print responses."""
    console.print(
        f"[bold magenta]🤖[/] [magenta]Instantiating A2A Client for: [bold]{entry.displayName}[/] ({entry.url})...[/]"
    )
    parsed_url = urlparse(entry.url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    relative_card_path = parsed_url.path

    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as http_client:
        resolver = A2ACardResolver(
            httpx_client=http_client,
            base_url=base_url,
        )
        agent_card = await resolver.get_agent_card(
            relative_card_path=relative_card_path
        )

        client_config = A2AClientConfig(
            httpx_client=http_client,
            supported_transports=[A2ATransport.jsonrpc, A2ATransport.http_json],
        )
        factory = A2AClientFactory(config=client_config)
        client = factory.create(agent_card)

        # Context ID tracking for session persistence
        context_id = None
        current_prompt = query

        console.print(
            Panel(
                f"[bold green]💬 Started multi-turn chat session with A2A Agent [bold]{entry.displayName}[/][/]\n"
                "[yellow]Type your requests below. Press Enter on an empty line to exit this session.[/]",
                title="A2A Agent Session",
                border_style="green",
            )
        )

        while True:
            request = A2AMessage(
                message_id=str(uuid.uuid4()),
                role="user",
                parts=[A2APart(text=current_prompt)],
                context_id=context_id,
            )

            console.print("\n[bold cyan]─── Agent Response Stream ───[/]")
            async for response in client.send_message(request):
                new_ctx_id = print_a2a_response(response)
                if new_ctx_id:
                    context_id = new_ctx_id
            console.print("\n[bold cyan]─────────────────────────────[/]")

            # Ask user for next turn input
            current_prompt = console.input(
                f"\n[bold yellow]Chat with {entry.displayName} (press Enter to exit): [/]"
            ).strip()
            if not current_prompt:
                break


async def main():
    console.print(
        Panel(
            "[bold white]ARD GENERIC RUNTIME CLIENT[/]",
            title="ARD + ADK Runtime",
            border_style="cyan",
        )
    )

    # 1. Check if registry server is running
    registry_url = ALLOWED_REGISTRIES[0]
    async with httpx.AsyncClient() as http_client:
        try:
            resp = await http_client.get(registry_url)
            if resp.status_code != 200:
                console.print(
                    f"[bold red]❌ Registry server returned status code {resp.status_code}[/]"
                )
                sys.exit(1)
        except httpx.NetworkError:
            console.print(
                f"[bold red]❌ Registry server is not running at {registry_url}.[/]"
            )
            console.print(
                "[bold yellow]👉 Please start the servers first using: uv run start-servers[/]"
            )
            sys.exit(1)

    # 2. Bootstrap ARD Registry Client
    console.print(
        f"[bold cyan]⚡[/] [cyan]Bootstrapping ARD Registry Client from {registry_url}...[/]"
    )
    manifest = await fetch_manifest(registry_url)

    async with ArdClient.from_manifest(manifest) as registry_client:
        console.print(
            "\n[bold green]✨ Ready! Enter queries to search, resolve, and connect to agents.[/]"
        )
        console.print("-" * 58)

        while True:
            try:
                query = console.input(
                    "\n[bold yellow]Enter search query/task (or press Enter to exit client): [/]"
                ).strip()
                if not query:
                    break

                console.print(
                    f"\n[bold blue]🔍[/] [blue]Searching ARD Registry Catalog for query: [italic]'{query}'[/]...[/]"
                )
                search_res = await registry_client.search(text=query)
                if not search_res.results:
                    console.print(
                        "[bold red]❌ No matching services discovered in registry.[/]"
                    )
                    continue

                # Rank and list results
                console.print("\n[bold cyan]🔍 Discovered Matches:[/]")
                for idx, entry in enumerate(search_res.results[:5]):
                    console.print(
                        f"  [bold cyan][{idx + 1}][/] [bold]{entry.displayName}[/] ([italic]{entry.type_}[/])"
                    )

                top_entry = search_res.results[0]
                console.print(
                    f"\n[bold green]🏆 Selected top match:[/] [green]{top_entry.displayName}[/]"
                )

                if top_entry.type_ in (
                    "application/mcp-server+json",
                    "application/mcp-server-card+json",
                ):
                    await handle_mcp_server(top_entry, query)
                elif top_entry.type_ == "application/a2a-agent-card+json":
                    await handle_a2a_server(top_entry, query)
                else:
                    console.print(
                        f"[bold red]❌ Unsupported catalog entry type: {top_entry.type_}[/]"
                    )

            except KeyboardInterrupt:
                break
            except Exception as e:
                console.print(f"\n[bold red]❌ Error during execution: {e}[/]")

        console.print("\n[bold green]👋 Exited client. Goodbye![/]")


def run_main():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[bold green]👋 Exited cleanly.[/]")


if __name__ == "__main__":
    run_main()
