from agent_finder_client.types import (
    Attestation,
    ProvenanceLink,
    TrustManifest,
    HostInfo,
    CatalogEntry,
    CatalogCollection,
    CapabilityManifest,
    QueryModel,
    SearchRequest,
    SearchResult,
    SearchResponse,
    ExploreFacetRequest,
    ExploreResultType,
    ExploreRequest,
    ExploreFacetBucket,
    ExploreFacetResult,
    ExploreResponse,
    CatalogEntryType,
    RegistryReferral,
    ListResponse,
    Error,
)
from agent_finder_client.client import (
    AgentFinderClient,
    AgentFinderException,
    AgentFinderError,
    AgentFinderHttpError,
    AgentFinderNetworkError,
    fetch_manifest,
)

__all__ = [
    "Attestation",
    "ProvenanceLink",
    "TrustManifest",
    "HostInfo",
    "CatalogEntry",
    "CatalogCollection",
    "CapabilityManifest",
    "QueryModel",
    "SearchRequest",
    "SearchResult",
    "SearchResponse",
    "ExploreFacetRequest",
    "ExploreResultType",
    "ExploreRequest",
    "ExploreFacetBucket",
    "ExploreFacetResult",
    "ExploreResponse",
    "CatalogEntryType",
    "RegistryReferral",
    "ListResponse",
    "Error",
    "AgentFinderClient",
    "AgentFinderException",
    "AgentFinderError",
    "AgentFinderHttpError",
    "AgentFinderNetworkError",
    "fetch_manifest",
    "__version__",
]

from importlib.metadata import version as _version

try:
    __version__ = _version("agent-finder-client")
except Exception:
    __version__ = "unknown"
