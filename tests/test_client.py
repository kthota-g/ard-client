from unittest.mock import AsyncMock, patch
import pytest
import httpx

from agent_finder_client import (
    AgentFinderClient,
    CapabilityManifest,
    SearchResponse,
    ExploreResultType,
    ExploreResponse,
    ExploreFacetRequest,
    ListResponse,
    fetch_manifest,
)

# The standard example from spec.md Section 4.1
EXAMPLE_MANIFEST_JSON = {
    "specVersion": "1.0",
    "host": {
        "displayName": "example Enterprise AI",
    },
    "entries": [
        {
            "identifier": "urn:ai:example.com:agent:assistant",
            "displayName": "Corporate Assistant (A2A)",
            "type": "application/a2a-agent-card+json",
            "url": "https://api.example.com/agents/assistant.json",
        }
    ],
}

EXAMPLE_SEARCH_RESPONSE_JSON = {
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

EXAMPLE_EXPLORE_RESPONSE_JSON = {
    "resultType": "facets",
    "facets": {
        "type": {
            "buckets": [{"value": "application/mcp-server+json", "count": 1247}],
            "otherCount": 23,
        }
    },
}


@pytest.mark.asyncio
async def test_async_client_fetch_manifest():
    req = httpx.Request("GET", "https://example.com/.well-known/ai-catalog.json")
    mock_response = httpx.Response(200, json=EXAMPLE_MANIFEST_JSON, request=req)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        # Test with URL
        manifest = await fetch_manifest(
            "https://example.com/.well-known/ai-catalog.json"
        )
        assert isinstance(manifest, CapabilityManifest)
        assert manifest.host.displayName == "example Enterprise AI"
        mock_get.assert_called_with("https://example.com/.well-known/ai-catalog.json")

        # Test with raw domain
        manifest2 = await fetch_manifest("example.com")
        assert manifest2.specVersion == "1.0"
        mock_get.assert_called_with("https://example.com/.well-known/ai-catalog.json")


@pytest.mark.asyncio
async def test_async_client_search():
    req = httpx.Request("POST", "https://registry.example.com/api/v1/search")
    mock_response = httpx.Response(200, json=EXAMPLE_SEARCH_RESPONSE_JSON, request=req)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        async with AgentFinderClient(
            base_url="https://registry.example.com/api/v1"
        ) as client:
            response = await client.search(
                text="find me a flight booking agent",
                filter_={
                    "type": ["application/a2a-agent-card+json"],
                    "compliance": "hipaa",
                },
                federation="referrals",
                page_size=5,
            )
            assert isinstance(response, SearchResponse)
            assert len(response.results) == 1
            assert response.results[0].score == 95
            assert response.pageToken == "token-123"

            # Verify payload construction
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            url = call_args[0][0]
            kwargs = call_args[1]

            assert url == "https://registry.example.com/api/v1/search"
            assert kwargs["json"]["query"]["text"] == "find me a flight booking agent"
            assert kwargs["json"]["query"]["filter"]["type"] == [
                "application/a2a-agent-card+json"
            ]
            assert kwargs["json"]["query"]["filter"]["compliance"] == ["hipaa"]
            assert kwargs["json"]["federation"] == "referrals"
            assert kwargs["json"]["pageSize"] == 5


@pytest.mark.asyncio
async def test_async_client_explore():
    req = httpx.Request("POST", "https://registry.example.com/api/v1/explore")
    mock_response = httpx.Response(200, json=EXAMPLE_EXPLORE_RESPONSE_JSON, request=req)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        async with AgentFinderClient(
            base_url="https://registry.example.com/api/v1"
        ) as client:
            result_type = ExploreResultType(
                facets=[ExploreFacetRequest(field="type", limit=10)]
            )
            response = await client.explore(
                result_type=result_type,
                text="currency conversion",
                filter_={"trustManifest.attestations.type": ["SOC2-Type2"]},
            )
            assert isinstance(response, ExploreResponse)
            assert response.resultType == "facets"
            assert "type" in response.facets
            assert (
                response.facets["type"].buckets[0].value
                == "application/mcp-server+json"
            )
            assert response.facets["type"].buckets[0].count == 1247
            assert response.facets["type"].otherCount == 23

            # Verify payload
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            url = call_args[0][0]
            kwargs = call_args[1]

            assert url == "https://registry.example.com/api/v1/explore"
            assert kwargs["json"]["query"]["text"] == "currency conversion"
            assert kwargs["json"]["query"]["filter"][
                "trustManifest.attestations.type"
            ] == ["SOC2-Type2"]
            assert kwargs["json"]["resultType"]["facets"][0]["field"] == "type"
            assert kwargs["json"]["resultType"]["facets"][0]["limit"] == 10


@pytest.mark.asyncio
async def test_async_client_list_agents():
    req = httpx.Request("GET", "https://registry.example.com/api/v1/agents")
    mock_response = httpx.Response(
        200,
        json={
            "items": [
                {
                    "identifier": "urn:ai:example.com:agent:assistant",
                    "displayName": "Corporate Assistant (A2A)",
                    "type": "application/a2a-agent-card+json",
                    "url": "https://api.example.com/agents/assistant.json",
                }
            ],
            "pageToken": "next-token-abc",
        },
        request=req,
    )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        async with AgentFinderClient(
            base_url="https://registry.example.com/api/v1"
        ) as client:
            resp = await client.list_agents(
                filter_expr="name == 'assistant'",
                order_by="name ASC",
                page_size=10,
                page_token="prev-token",
            )
            assert isinstance(resp, ListResponse)
            assert len(resp.items) == 1
            assert resp.items[0].identifier == "urn:ai:example.com:agent:assistant"
            assert resp.pageToken == "next-token-abc"

            mock_get.assert_called_once_with(
                "https://registry.example.com/api/v1/agents",
                params={
                    "filter": "name == 'assistant'",
                    "orderBy": "name ASC",
                    "pageSize": "10",
                    "pageToken": "prev-token",
                },
            )


@pytest.mark.asyncio
async def test_base_url_auto_prefixing():
    client = AgentFinderClient(base_url="registry.example.com/api/v1")
    assert client.base_url == "https://registry.example.com/api/v1"

    client2 = AgentFinderClient(base_url="http://localhost:8080")
    assert client2.base_url == "http://localhost:8080"


@pytest.mark.asyncio
async def test_intelligent_fetch_manifest_url_parsing():
    mock_response = httpx.Response(200, json=EXAMPLE_MANIFEST_JSON)
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        # With path and no scheme: should just prefix with https://
        await fetch_manifest("example.com/custom/path.json")
        mock_get.assert_called_with("https://example.com/custom/path.json")

        # With path and scheme: should remain unchanged
        await fetch_manifest("http://example.com/custom/path.json")
        mock_get.assert_called_with("http://example.com/custom/path.json")


@pytest.mark.asyncio
async def test_custom_error_handling():
    from agent_finder_client import AgentFinderError

    error_json = {
        "errorCode": "INVALID_ARGUMENT",
        "message": "The filter expression is malformed.",
    }
    mock_response = httpx.Response(400, json=error_json)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        with pytest.raises(AgentFinderError) as exc_info:
            await fetch_manifest("example.com")

        assert exc_info.value.status_code == 400
        assert exc_info.value.error_code == "INVALID_ARGUMENT"
        assert "The filter expression is malformed" in exc_info.value.message


@pytest.mark.asyncio
async def test_client_from_manifest():
    from agent_finder_client import CapabilityManifest

    # Create a mock CapabilityManifest with a registry entry
    manifest_data = {
        "specVersion": "1.0",
        "host": {"displayName": "Test AI"},
        "entries": [
            {
                "identifier": "urn:ai:example.com:registry:global",
                "displayName": "Global Registry",
                "type": "application/ai-registry+json",
                "url": "https://registry.example.com/api/v1/",
            },
            {
                "identifier": "urn:ai:example.com:agent:my-agent",
                "displayName": "My Agent",
                "type": "application/a2a-agent-card+json",
                "url": "https://example.com/agent.json",
            },
        ],
    }
    manifest = CapabilityManifest.from_dict(manifest_data)

    # 1. Create client by matching first/only registry entry
    client = AgentFinderClient.from_manifest(manifest)
    assert client.base_url == "https://registry.example.com/api/v1"

    # 2. Create client by matching specific URN identifier
    client2 = AgentFinderClient.from_manifest(
        manifest, "urn:ai:example.com:registry:global"
    )
    assert client2.base_url == "https://registry.example.com/api/v1"

    # 3. Error raised when identifier is not found
    with pytest.raises(ValueError) as exc_info:
        AgentFinderClient.from_manifest(
            manifest, "urn:ai:example.com:registry:not-exist"
        )
    assert "No registry entry with identifier" in str(exc_info.value)

    # 4. Error raised when manifest has no registry entries
    no_registry_manifest_data = {
        "specVersion": "1.0",
        "host": {"displayName": "Test AI"},
        "entries": [
            {
                "identifier": "urn:ai:example.com:agent:my-agent",
                "displayName": "My Agent",
                "type": "application/a2a-agent-card+json",
                "url": "https://example.com/agent.json",
            }
        ],
    }
    no_reg_manifest = CapabilityManifest.from_dict(no_registry_manifest_data)
    with pytest.raises(ValueError) as exc_info2:
        AgentFinderClient.from_manifest(no_reg_manifest)
    assert "No registry entries" in str(exc_info2.value)


@pytest.mark.asyncio
async def test_client_http_error_wrapping():
    from agent_finder_client import AgentFinderHttpError, AgentFinderException

    # Setup mock post to raise HTTPStatusError when raise_for_status is called
    req = httpx.Request("POST", "https://registry.example.com/api/v1/search")
    mock_response = httpx.Response(500, text="Internal Server Error", request=req)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        async with AgentFinderClient(
            base_url="https://registry.example.com/api/v1"
        ) as client:
            with pytest.raises(AgentFinderHttpError) as exc_info:
                await client.search("test")

            assert issubclass(AgentFinderHttpError, AgentFinderException)
            assert exc_info.value.status_code == 500
            assert "HTTP 500" in str(exc_info.value)


@pytest.mark.asyncio
async def test_client_network_error_wrapping():
    from agent_finder_client import AgentFinderNetworkError, AgentFinderException

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.ConnectError("Connection refused")

        async with AgentFinderClient(
            base_url="https://registry.example.com/api/v1"
        ) as client:
            with pytest.raises(AgentFinderNetworkError) as exc_info:
                await client.search("test")

            assert issubclass(AgentFinderNetworkError, AgentFinderException)
            assert "Network error during registry request" in str(exc_info.value)
            assert isinstance(exc_info.value.original_exception, httpx.ConnectError)


@pytest.mark.asyncio
async def test_fetch_manifest_http_error_wrapping():
    from agent_finder_client import AgentFinderHttpError

    # Setup mock response returning a plain text 404 error
    req = httpx.Request("GET", "https://example.com/.well-known/ai-catalog.json")
    mock_response = httpx.Response(404, text="Not Found", request=req)
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        with pytest.raises(AgentFinderHttpError) as exc_info:
            await fetch_manifest("example.com")

        assert exc_info.value.status_code == 404
        assert "404" in str(exc_info.value)


@pytest.mark.asyncio
async def test_fetch_manifest_network_error_wrapping():
    from agent_finder_client import AgentFinderNetworkError

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(AgentFinderNetworkError) as exc_info:
            await fetch_manifest("example.com")

        assert "Network error while fetching manifest" in str(exc_info.value)
        assert isinstance(exc_info.value.original_exception, httpx.ConnectError)


@pytest.mark.asyncio
async def test_client_custom_client_configuration():
    custom_headers = {
        "Authorization": "Bearer test-token",
        "X-Client-Name": "agent-finder-client-test",
    }
    custom_timeout = httpx.Timeout(15.0)

    req = httpx.Request("POST", "https://registry.example.com/api/v1/search")
    mock_response = httpx.Response(200, json=EXAMPLE_SEARCH_RESPONSE_JSON, request=req)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        async with httpx.AsyncClient(
            headers=custom_headers, timeout=custom_timeout
        ) as async_client:
            # Verify client setup
            assert async_client.headers["Authorization"] == "Bearer test-token"
            assert async_client.headers["X-Client-Name"] == "agent-finder-client-test"
            assert async_client.timeout.read == 15.0

            # Pass custom client to AgentFinderClient
            async with AgentFinderClient(
                base_url="https://registry.example.com/api/v1", client=async_client
            ) as client:
                assert client._client is async_client
                assert not client._own_client  # verify client ownership is not claimed

                # Execute search call
                response = await client.search("test query")
                assert isinstance(response, SearchResponse)

                # Verify the request was made to the correct URL
                mock_post.assert_called_once()
                assert (
                    mock_post.call_args[0][0]
                    == "https://registry.example.com/api/v1/search"
                )
