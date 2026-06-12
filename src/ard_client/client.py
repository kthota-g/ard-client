import httpx
from urllib.parse import urlparse
from typing import List, Dict, Literal

from ard_client.types import (
    CapabilityManifest,
    ExploreRequest,
    ExploreResultType,
    ExploreResponse,
    ListResponse,
    QueryModel,
    SearchRequest,
    SearchResponse,
)


class ArdException(Exception):
    """Base exception for all ARD SDK errors."""


class ArdError(ArdException):
    """Custom exception raised when the ARD API returns a structured error response."""

    def __init__(self, status_code: int, error_code: str, message: str):
        super().__init__(f"[{error_code}] {message} (HTTP {status_code})")
        self.status_code = status_code
        self.error_code = error_code
        self.message = message


class ArdHttpError(ArdException):
    """Exception raised for generic HTTP error status codes not having structured API errors."""

    def __init__(self, status_code: int, message: str, response: httpx.Response):
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code
        self.response = response


class ArdNetworkError(ArdException):
    """Exception raised for network-level issues (e.g., DNS resolution, connection timeout)."""

    def __init__(self, message: str, original_exception: Exception):
        super().__init__(message)
        self.original_exception = original_exception


async def _raise_for_status(response: httpx.Response) -> None:
    """Raise appropriate ArdException subclass for non-success HTTP responses."""
    if response.is_success:
        return

    try:
        data = response.json()
        if isinstance(data, dict) and "errorCode" in data and "message" in data:
            raise ArdError(
                status_code=response.status_code,
                error_code=data["errorCode"],
                message=data["message"],
            )
    except (ValueError, KeyError):
        pass

    response.raise_for_status()


async def fetch_manifest(
    url_or_domain: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> CapabilityManifest:
    """
    Fetch a static capability manifest (ai-catalog.json) from a given URL or domain.

    If a domain is provided (e.g., "example.com"), it automatically queries the well-known path:
    "https://example.com/.well-known/ai-catalog.json".
    """
    url = url_or_domain.strip()
    parsed = urlparse(url)
    if not parsed.scheme:
        if "/" in url:
            url = f"https://{url}"
        else:
            url = f"https://{url}/.well-known/ai-catalog.json"
    else:
        if not parsed.path or parsed.path == "/":
            url = f"{parsed.scheme}://{parsed.netloc}/.well-known/ai-catalog.json"
            if parsed.query:
                url += f"?{parsed.query}"

    _client = client or httpx.AsyncClient(follow_redirects=True)
    try:
        try:
            response = await _client.get(url)
            await _raise_for_status(response)
            return CapabilityManifest.from_dict(response.json())
        except httpx.HTTPStatusError as e:
            raise ArdHttpError(
                status_code=e.response.status_code,
                message=str(e),
                response=e.response,
            ) from e
        except httpx.RequestError as e:
            raise ArdNetworkError(
                message=f"Network error while fetching manifest from {url}: {str(e)}",
                original_exception=e,
            ) from e
    finally:
        if client is None:
            await _client.aclose()


class ArdClient:
    """Asynchronous client for consuming the ARD API (both static discovery and dynamic registries)."""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ):
        """
        Initialize the Asynchronous ARD Client.

        :param base_url: The base URL of the Agent Registry (e.g., "https://registry.example.com/api/v1/").
        :param client: An optional pre-configured httpx.AsyncClient instance.
        """
        if base_url:
            base_url = base_url.rstrip("/")
            if not base_url.startswith(("http://", "https://")):
                base_url = f"https://{base_url}"

            for suffix in ("/search", "/explore", "/agents"):
                if base_url.endswith(suffix):
                    base_url = base_url[: -len(suffix)]
                    break
        self.base_url = base_url
        self._client = client or httpx.AsyncClient(follow_redirects=True)
        self._own_client = client is None

    @classmethod
    def from_manifest(
        cls,
        manifest: CapabilityManifest,
        identifier: str | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> "ArdClient":
        """
        Create an ArdClient from a CapabilityManifest by finding an advertised AI registry.

        :param manifest: The CapabilityManifest containing capability and registry entries.
        :param identifier: Optional. The specific URN identifier of the registry entry to use.
                           If not specified, the first registry entry found will be used.
        :param client: Optional pre-configured httpx.AsyncClient instance.
        :return: An initialized ArdClient.
        :raises ValueError: If no suitable registry entry is found in the manifest.
        """
        registry_entries = [
            entry
            for entry in manifest.entries
            if entry.type_ == "application/ai-registry+json"
            or entry.type_ == "application/ai-registry"
        ]

        if not registry_entries:
            raise ValueError(
                "No registry entries ('application/ai-registry+json') found in the capability manifest."
            )

        selected_entry = None
        if identifier:
            for entry in registry_entries:
                if entry.identifier == identifier:
                    selected_entry = entry
                    break
            if not selected_entry:
                raise ValueError(
                    f"No registry entry with identifier '{identifier}' found in the capability manifest."
                )
        else:
            selected_entry = registry_entries[0]

        if not selected_entry.url:
            raise ValueError(
                f"Selected registry entry '{selected_entry.identifier}' does not define a 'url'."
            )

        return cls(base_url=selected_entry.url, client=client)

    async def close(self) -> None:
        """Close the underlying HTTP client if it was created by this client."""
        if self._own_client:
            await self._client.aclose()

    async def __aenter__(self) -> "ArdClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def _send_request(self, method_func, url, **kwargs) -> httpx.Response:
        """Internal helper to execute requests with complete HTTP and network error wrapping."""
        try:
            response = await method_func(url, **kwargs)
            await _raise_for_status(response)
            return response
        except httpx.HTTPStatusError as e:
            raise ArdHttpError(
                status_code=e.response.status_code,
                message=str(e),
                response=e.response,
            ) from e
        except httpx.RequestError as e:
            raise ArdNetworkError(
                message=f"Network error during registry request to {url}: {str(e)}",
                original_exception=e,
            ) from e

    async def search(
        self,
        text: str,
        *,
        filter_: Dict[str, List[str]] | None = None,
        federation: Literal["auto", "referrals", "none"] | str | None = None,
        page_size: int | None = None,
        page_token: str | None = None,
    ) -> SearchResponse:
        """
        Search the dynamic ARD Registry for capabilities matching a natural language query.

        :param text: Required. Natural language description of the need.
        :param filter_: Optional. Structured constraints dictionary.
        :param federation: Optional. auto (default), referrals, or none.
        :param page_size: Optional. Max number of search results to return.
        :param page_token: Optional. Pagination token for sequential searches.
        """
        if not self.base_url:
            raise ValueError("base_url must be specified to execute dynamic searches")

        query = QueryModel(text=text, filter_=filter_)
        request_payload = SearchRequest(
            query=query,
            federation=federation or "auto",
            pageSize=page_size or 10,
            pageToken=page_token,
        )

        response = await self._send_request(
            self._client.post,
            f"{self.base_url}/search",
            json=request_payload.to_dict(),
            headers={"Content-Type": "application/json"},
        )
        return SearchResponse.from_dict(response.json())

    async def explore(
        self,
        result_type: ExploreResultType,
        *,
        text: str | None = None,
        filter_: Dict[str, List[str]] | None = None,
    ) -> ExploreResponse:
        """
        Introspect registry statistics and aggregation facets.

        :param result_type: Required. Configures the aggregated facets to compute.
        :param text: Optional. Natural language query constraint.
        :param filter_: Optional. Structured constraints query filter.
        """
        if not self.base_url:
            raise ValueError(
                "base_url must be specified to execute registry exploration"
            )

        query = QueryModel(text=text, filter_=filter_) if text else None
        request_payload = ExploreRequest(query=query, resultType=result_type)

        response = await self._send_request(
            self._client.post,
            f"{self.base_url}/explore",
            json=request_payload.to_dict(),
            headers={"Content-Type": "application/json"},
        )
        return ExploreResponse.from_dict(response.json())

    async def list_agents(
        self,
        *,
        filter_expr: str | None = None,
        order_by: str | None = None,
        page_size: int | None = None,
        page_token: str | None = None,
    ) -> ListResponse:
        """
        List/browse capabilities deterministically from the registry (GET /agents endpoint).

        :param filter_expr: EBNF filter expression.
        :param order_by: Sorting fields (e.g., "displayName", "updatedAt DESC").
        :param page_size: Max results (default: 20, max: 100).
        :param page_token: Pagination token.
        :return: A fully validated ListResponse object containing matching items, pageToken and totals.
        """
        if not self.base_url:
            raise ValueError("base_url must be specified to list agents")

        params = {}
        if filter_expr is not None:
            params["filter"] = filter_expr
        if order_by is not None:
            params["orderBy"] = order_by
        if page_size is not None:
            params["pageSize"] = str(page_size)
        if page_token is not None:
            params["pageToken"] = page_token

        response = await self._send_request(
            self._client.get,
            f"{self.base_url}/agents",
            params=params,
        )
        return ListResponse.from_dict(response.json())
