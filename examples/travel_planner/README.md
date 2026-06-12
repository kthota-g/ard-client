# ✈️ Travel Planner Agent Example

This example demonstrates how an interactive client application can dynamically discover, resolve, and connect to domain-specific services (e.g. currency converter MCP servers, travel advisor A2A agents) registered in an **Agentic Resource Discovery (ARD)** compliant catalog.

---

## 🌟 How it Works

1. **Local ARD Registry Server**: Implements the ARD standard:
   - Serves a capability manifest (`/.well-known/ai-catalog.json`) advertising the registry.
   - Serves a search endpoint (`POST /api/v1/search`) that matches natural language queries and tags.
2. **Standard MCP Server**: Exposes currency conversion tools over streamable HTTP.
3. **A2A Travel Agent Server**: Powered by Google ADK. Resolves client connections over SSE/HTTP to plan itineraries and search flights/hotels.
4. **Generic Rich Client**:
   - Boots from the registry, searches for matching capabilities based on user input.
   - Connects to the resolved resource over its native protocol (MCP or A2A).
   - Manages interactive tool parameter inputs for MCP or a persistent multi-turn chat session for A2A.

---

## 🚀 Running the Example

Make sure you have `uv` installed. Follow these steps:

### Step 1: Start the Servers
Start the registry, currency MCP server, and A2A travel advisor service:

```bash
uv run --package travel-planner start-servers
```

This spins up the following local endpoints:
- **Registry Host:** `http://127.0.0.1:8500/.well-known/ai-catalog.json`
- **Currency MCP Service:** `http://127.0.0.1:8501/mcp`
- **A2A Travel Advisor:** `http://127.0.0.1:8502/.well-known/agent-card.json`

### Step 2: Run the Client
In a separate terminal, export your `GEMINI_API_KEY` and run the interactive CLI client:

```bash
export GEMINI_API_KEY="your-api-key-here"
uv run --package travel-planner client
```

---

## 📋 Interactive Usage Examples

### 1. Currency Conversion (MCP Tool)
Type `currency` in the search query, select the `convert_currency` tool, and provide argument values interactively:

```text
Enter search query/task (or press Enter to exit client): currency

🔍 Searching ARD Registry Catalog for query: 'currency'...

🔍 Discovered Matches:
  [1] Forex FX Converter (application/mcp-server+json)

🏆 Selected top match: Forex FX Converter
🔌 Instantiating MCP Client for: Forex FX Converter (http://127.0.0.1:8501/mcp)...

🔧 Available Tools:
  [1] convert_currency: Convert money from one currency to another using mock real-time rates.

Select tool to invoke (1-1): 1

✅ Selected Tool: convert_currency

✍️  Please provide values for the arguments:
  - from_currency (string) (Required): USD
  - to_currency (string) (Required): JPY
  - amount (number) (Required): 1000

⚡ Invoking tool convert_currency with arguments: {'from_currency': 'USD', 'to_currency': 'JPY', 'amount': 1000.0}...

✨ Result:
1000.0 USD = 160197.00 JPY (Rate: 160.1970)
```

### 2. Travel Planning (A2A Multi-Turn Session)
Type `travel planner` in the search query to resolve the A2A Travel Advisor and start a multi-turn chat session:

```text
Enter search query/task (or press Enter to exit client): travel planner

🔍 Searching ARD Registry Catalog for query: 'travel planner'...

🔍 Discovered Matches:
  [1] A2A Travel Advisor (application/a2a-agent-card+json)
  [2] Forex FX Converter (application/mcp-server+json)

🏆 Selected top match: A2A Travel Advisor
🤖 Instantiating A2A Client for: A2A Travel Advisor (http://127.0.0.1:8502/.well-known/agent-card.json)...
╭───────────────────────────────────────────────────────────────── A2A Agent Session ──────────────────────────────────────────────────────────────────╮
│ 💬 Started multi-turn chat session with A2A Agent A2A Travel Advisor                                                                                 │
│ Type your requests below. Press Enter on an empty line to exit this session.                                                                         │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

─── Agent Response Stream ───
Hello! I'm your premium travel coordinator. I'd be delighted to help you plan an unforgettable journey.
...
```
