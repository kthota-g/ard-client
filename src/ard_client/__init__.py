from ard_client.types import (
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
from ard_client.client import (
    ArdClient,
    ArdException,
    ArdError,
    ArdHttpError,
    ArdNetworkError,
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
    "ArdClient",
    "ArdException",
    "ArdError",
    "ArdHttpError",
    "ArdNetworkError",
    "fetch_manifest",
    "__version__",
]

from importlib.metadata import version as _version

try:
    __version__ = _version("ard-client")
except Exception:
    __version__ = "unknown"
