import json
import pytest
from agent_finder_client.types import (
    CapabilityManifest,
    CatalogEntry,
    SearchRequest,
    QueryModel,
    SearchResponse,
    CatalogEntryType,
)

# The standard example from spec.md Section 4.1
EXAMPLE_MANIFEST = """{
  "specVersion": "1.0",
  "host": {
    "displayName": "example Enterprise AI",
    "identifier": "did:web:example.com"
  },
  "entries": [
    {
      "identifier": "urn:ai:example.com:agent:assistant",
      "displayName": "Corporate Assistant (A2A)",
      "type": "application/a2a-agent-card+json",
      "url": "https://api.example.com/agents/assistant.json",
      "description": "General-purpose corporate A2A assistant.",
      "representativeQueries": [
        "help me draft an email to the security working group",
        "summarize my unread messages from Todd"
      ]
    },
    {
      "identifier": "urn:ai:example.com:server:weather",
      "displayName": "Weather Data Node",
      "type": "application/mcp-server+json",
      "url": "https://api.example.com/mcp/weather.json",
      "capabilities": ["WeatherTool", "ForecastTool"],
      "description": "Enterprise weather MCP server for live telemetry.",
      "representativeQueries": [
        "what is the current wind speed in Chicago",
        "get the 5-day forecast for Seattle"
      ]
    },
    {
      "identifier": "urn:ai:example.com:plugin:finance-suite",
      "displayName": "Finance Tool Bundle",
      "type": "application/ai-catalog+json",
      "description": "A static nested bundle containing an A2A agent and its required market dataset.",
      "tags": ["finance", "bundle"],
      "data": {
        "specVersion": "1.0",
        "entries": [
          {
            "identifier": "urn:ai:example.com:finance:a2a",
            "displayName": "Finance Trading Agent",
            "type": "application/a2a-agent-card+json",
            "url": "https://api.example.com/agents/finance-trader.json"
          },
          {
            "identifier": "urn:ai:example.com:market:2026",
            "displayName": "Market Dataset 2026",
            "type": "application/parquet",
            "url": "https://data.example.com/market-2026.parquet"
          }
        ]
      }
    },
    {
      "identifier": "urn:ai:example.com:registry:global",
      "displayName": "example Global Agent Registry",
      "type": "application/ai-registry+json",
      "url": "https://registry.example.com/api/v1/",
      "description": "Dynamic REST API search interface to discover all approved enterprise agents.",
      "tags": ["registry", "search", "dynamic"],
      "trustManifest": {
        "identity": "spiffe://example.com/registry/global",
        "identityType": "spiffe",
        "attestations": [
          {
            "type": "SPIFFE-X509",
            "uri": "https://example.com/.well-known/spiffe/jwks",
            "mediaType": "application/json"
          },
          {
            "type": "SOC2-Type2",
            "uri": "https://trust.example.com/reports/soc2.pdf",
            "mediaType": "application/pdf"
          }
        ]
      }
    }
  ],
  "collections": [
    {
      "displayName": "Engineering Department Catalogs",
      "url": "https://example.com/catalogs/engineering.json",
      "description": "Sub-catalogs containing CI/CD and internal deployment agents."
    }
  ]
}"""


def test_manifest_parsing():
    data = json.loads(EXAMPLE_MANIFEST)
    manifest = CapabilityManifest.from_dict(data)

    # Validate fields
    assert manifest.specVersion == "1.0"
    assert manifest.host.displayName == "example Enterprise AI"
    assert manifest.host.identifier == "did:web:example.com"
    assert len(manifest.entries) == 4

    # Check the first entry
    entry1 = manifest.entries[0]
    assert entry1.identifier == "urn:ai:example.com:agent:assistant"
    assert entry1.displayName == "Corporate Assistant (A2A)"
    assert entry1.type_ == "application/a2a-agent-card+json"
    assert entry1.url == "https://api.example.com/agents/assistant.json"
    assert entry1.data is None
    assert "draft an email" in entry1.representativeQueries[0]

    # Check nested data (the third entry has data)
    entry3 = manifest.entries[2]
    assert entry3.identifier == "urn:ai:example.com:plugin:finance-suite"
    assert entry3.data is not None
    assert entry3.url is None
    assert entry3.data["specVersion"] == "1.0"
    assert len(entry3.data["entries"]) == 2

    # Check trustManifest (the fourth entry)
    entry4 = manifest.entries[3]
    assert entry4.trustManifest is not None
    assert entry4.trustManifest.identity == "spiffe://example.com/registry/global"
    assert len(entry4.trustManifest.attestations) == 2
    assert entry4.trustManifest.attestations[0].type_ == "SPIFFE-X509"

    # Check collections
    assert len(manifest.collections) == 1
    assert manifest.collections[0].displayName == "Engineering Department Catalogs"

    # Re-serialize and parse to make sure it matches
    serialized = manifest.to_dict()

    # Verify that JSON output still uses "type" key
    assert serialized["entries"][0]["type"] == "application/a2a-agent-card+json"
    assert (
        serialized["entries"][3]["trustManifest"]["attestations"][0]["type"]
        == "SPIFFE-X509"
    )

    reparsed = CapabilityManifest.from_dict(serialized)
    assert reparsed.specVersion == manifest.specVersion
    assert len(reparsed.entries) == len(manifest.entries)
    print("test_manifest_parsing passed successfully!")


def test_validation_constraints():
    # Exact one of url or data - should succeed
    c1 = CatalogEntry(
        identifier="urn:ai:test.com:namespace:ok",
        displayName="Ok",
        type_="application/json",
        url="https://ok.com",
    )
    assert c1.url == "https://ok.com"

    c2 = CatalogEntry(
        identifier="urn:ai:test.com:namespace:ok2",
        displayName="Ok2",
        type_="application/json",
        data={"some": "data"},
    )
    assert c2.data == {"some": "data"}

    # Neither - should raise ValueError
    try:
        CatalogEntry(
            identifier="urn:ai:test.com:namespace:fail",
            displayName="Fail",
            type_="application/json",
        )
        assert False, "Should have raised ValueError for neither url nor data"
    except ValueError as e:
        assert "exactly one of 'url' or 'data'" in str(e)

    # Both - should raise ValueError
    try:
        CatalogEntry(
            identifier="urn:ai:test.com:namespace:fail2",
            displayName="Fail2",
            type_="application/json",
            url="https://ok.com",
            data={"some": "data"},
        )
        assert False, "Should have raised ValueError for both url and data"
    except ValueError as e:
        assert "exactly one of 'url' or 'data'" in str(e)

    print("test_validation_constraints passed successfully!")


def test_search_types():
    search_req_dict = {
        "query": {
            "text": "find me a flight booking agent",
            "filter": {
                "type": ["application/a2a-agent-card+json"],
                "compliance": "hipaa",
            },
        },
        "federation": "referrals",
        "pageSize": 5,
    }
    req = SearchRequest.from_dict(search_req_dict)
    assert req.query.text == "find me a flight booking agent"
    assert req.query.filter_["type"] == ["application/a2a-agent-card+json"]
    assert req.query.filter_["compliance"] == ["hipaa"]
    assert req.federation == "referrals"
    assert req.pageSize == 5

    serialized = req.to_dict()
    assert serialized["query"]["text"] == "find me a flight booking agent"
    assert serialized["query"]["filter"]["type"] == ["application/a2a-agent-card+json"]
    assert serialized["query"]["filter"]["compliance"] == ["hipaa"]
    assert serialized["federation"] == "referrals"
    assert serialized["pageSize"] == 5

    search_resp_dict = {
        "results": [
            {
                "identifier": "urn:ai:example.com:agent:assistant",
                "displayName": "Corporate Assistant (A2A)",
                "type": "application/a2a-agent-card+json",
                "url": "https://api.example.com/agents/assistant.json",
                "score": 95,
                "source": "https://registry.example.com/api/v1/",
            }
        ],
        "referrals": [
            {
                "identifier": "urn:ai:nlweb.ai:registry:public",
                "displayName": "Public Agent Finder",
                "type": "application/ai-registry",
                "url": "https://finder.nlweb.ai/search",
            }
        ],
        "pageToken": "token-123",
    }

    resp = SearchResponse.from_dict(search_resp_dict)
    assert len(resp.results) == 1
    assert resp.results[0].score == 95
    assert resp.results[0].source == "https://registry.example.com/api/v1/"
    assert resp.results[0].identifier == "urn:ai:example.com:agent:assistant"
    assert resp.results[0].type_ == "application/a2a-agent-card+json"
    assert len(resp.referrals) == 1
    assert resp.referrals[0].identifier == "urn:ai:nlweb.ai:registry:public"
    assert resp.referrals[0].type_ == "application/ai-registry"
    assert resp.pageToken == "token-123"

    print("test_search_types passed successfully!")


def test_extra_fields():
    # Instantiate a model with extra attributes
    c = CatalogEntry(
        identifier="urn:ai:test.com:namespace:extra",
        displayName="Extra Test",
        type_="application/json",
        url="https://extra.com",
        custom_key="custom_value",
        another_extra=42,
    )
    # Verify that they are accessible via attribute lookup
    assert c.custom_key == "custom_value"
    assert c.another_extra == 42

    # Verify that to_dict preserves them
    serialized = c.to_dict()
    assert serialized["custom_key"] == "custom_value"
    assert serialized["another_extra"] == 42

    # Verify from_dict preserves them as well
    reparsed = CatalogEntry.from_dict(serialized)
    assert reparsed.custom_key == "custom_value"
    assert reparsed.another_extra == 42

    print("test_extra_fields passed successfully!")


def test_catalog_entry_type_enum():
    # 1. Verify enum resolution and value equality with well-known media type
    c1 = CatalogEntry(
        identifier="urn:ai:test.com:namespace:enum1",
        displayName="Enum Test 1",
        type_="application/a2a-agent-card+json",
        url="https://test1.com",
    )
    assert c1.type_ == CatalogEntryType.A2A_AGENT_CARD
    assert c1.type_ == "application/a2a-agent-card+json"

    # Re-serialization test
    serialized1 = c1.to_dict()
    assert serialized1["type"] == "application/a2a-agent-card+json"

    # 2. Verify extensible fallback to custom media type string
    c2 = CatalogEntry(
        identifier="urn:ai:test.com:namespace:enum2",
        displayName="Enum Test 2",
        type_="application/custom-protocol+json",
        url="https://test2.com",
    )
    assert c2.type_ == "application/custom-protocol+json"

    serialized2 = c2.to_dict()
    assert serialized2["type"] == "application/custom-protocol+json"

    print("test_catalog_entry_type_enum passed successfully!")


def test_query_model_filter_coercion():
    # 1. Coerces scalar string, int, float, bool to lists of strings (with standard lowercase booleans)
    q = QueryModel(
        text="test query",
        filter={
            "str_key": "value",
            "int_key": 42,
            "float_key": 3.14,
            "bool_key": True,
            "none_key": None,
        },
    )
    assert q.filter_ == {
        "str_key": ["value"],
        "int_key": ["42"],
        "float_key": ["3.14"],
        "bool_key": ["true"],
        "none_key": [],
    }

    # 2. Coerces list of mixed types to list of strings
    q2 = QueryModel(
        text="test query 2",
        filter={
            "mixed_key": ["val1", 100, False, None],
        },
    )
    assert q2.filter_ == {
        "mixed_key": ["val1", "100", "false"],
    }

    # 3. Verifies to_dict produces correct structure
    serialized = q.to_dict()
    assert serialized["filter"]["int_key"] == ["42"]
    assert serialized["filter"]["bool_key"] == ["true"]

    print("test_query_model_filter_coercion passed successfully!")


def test_urn_validation():
    from pydantic import ValidationError

    # 1. 1-colon URN (no-namespace) - should pass!
    c1 = CatalogEntry(
        identifier="urn:ai:example.com:weather-server",
        displayName="Weather Server",
        type_="application/mcp-server+json",
        url="https://example.com/mcp.json",
    )
    assert c1.identifier == "urn:ai:example.com:weather-server"

    # 2. 2-colon URN (with namespace) - should pass!
    c2 = CatalogEntry(
        identifier="urn:ai:example.com:agent:assistant",
        displayName="Assistant",
        type_="application/a2a-agent-card+json",
        url="https://example.com/agent.json",
    )
    assert c2.identifier == "urn:ai:example.com:agent:assistant"

    # 3. 3-colon URN (hierarchical namespace) - should pass!
    c3 = CatalogEntry(
        identifier="urn:ai:example.com:finance:trading:a2a",
        displayName="Finance Agent",
        type_="application/a2a-agent-card+json",
        url="https://example.com/finance.json",
    )
    assert c3.identifier == "urn:ai:example.com:finance:trading:a2a"

    # 4. Malformed URN missing publisher/domain - should fail
    with pytest.raises(ValidationError):
        CatalogEntry(
            identifier="urn:ai:example",
            displayName="Fail",
            type_="application/json",
            url="https://fail.com",
        )

    # 5. Malformed URN missing urn:ai prefix - should fail
    with pytest.raises(ValidationError):
        CatalogEntry(
            identifier="did:web:example.com",
            displayName="Fail",
            type_="application/json",
            url="https://fail.com",
        )

    print("test_urn_validation passed successfully!")


if __name__ == "__main__":
    test_manifest_parsing()
    test_validation_constraints()
    test_search_types()
    test_extra_fields()
    test_catalog_entry_type_enum()
    test_query_model_filter_coercion()
    test_urn_validation()
    print("All types tests completed successfully!")
