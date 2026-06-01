from enum import StrEnum
from typing import Any, Dict, List, Literal, Self
from pydantic import BaseModel, ConfigDict, Field, model_validator


class BaseModelWithAlias(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
        extra="allow",
    )

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Self:
        return cls.model_validate(data)


class CatalogEntryType(StrEnum):
    """Well-known IANA media types for AI catalog entries and registries."""
    AI_CATALOG = "application/ai-catalog+json"
    A2A_AGENT_CARD = "application/a2a-agent-card+json"
    MCP_SERVER_CARD = "application/mcp-server-card+json"
    AI_REGISTRY = "application/ai-registry+json"


class Attestation(BaseModelWithAlias):
    """Provides verifiable proof of a claim (e.g., compliance certifications)."""
    type_: str = Field(alias="type")
    uri: str
    mediaType: str
    digest: str | None = None


class ProvenanceLink(BaseModelWithAlias):
    """Cryptographic lineage trail of the artifact."""
    relation: Literal["derivedFrom", "publishedFrom", "copiedFrom"] | str
    sourceId: str
    sourceDigest: str | None = None


class TrustManifest(BaseModelWithAlias):
    """Zero-trust security, identity, and compliance envelope metadata."""
    identity: str
    identityType: Literal["spiffe", "did", "https", "other"] | str | None = None
    attestations: List[Attestation] | None = None
    provenance: List[ProvenanceLink] | None = None
    signature: str | None = None


class HostInfo(BaseModelWithAlias):
    """Information about the catalog publisher or hosting entity."""
    displayName: str
    identifier: str | None = None
    documentationUrl: str | None = None
    logoUrl: str | None = None
    trustManifest: TrustManifest | None = None


class CatalogEntry(BaseModelWithAlias):
    """A single entry in the capability manifest representing an agent or capability."""
    identifier: str = Field(pattern=r"^urn:ai:[a-zA-Z0-9.-]+(:[a-zA-Z0-9.-]+)+$")
    displayName: str
    type_: CatalogEntryType | str = Field(alias="type")
    url: str | None = None
    data: Any | None = None  # Embedded JSON object containing the full artifact document
    description: str | None = None
    tags: List[str] | None = None
    capabilities: List[str] | None = None
    representativeQueries: List[str] | None = Field(default=None, min_length=2, max_length=5)
    version: str | None = None
    updatedAt: str | None = None
    metadata: Dict[str, str | int | float | bool | None] | None = None
    trustManifest: TrustManifest | None = None

    @model_validator(mode="after")
    def validate_value_or_reference(self) -> Self:
        url_present = self.url is not None
        data_present = self.data is not None

        if (not url_present and not data_present) or (url_present and data_present):
            raise ValueError("CatalogEntry must contain exactly one of 'url' or 'data'")
        return self


class CatalogCollection(BaseModelWithAlias):
    """Lists nested or related catalogs."""
    url: str  # Required
    displayName: str | None = None
    description: str | None = None


class CapabilityManifest(BaseModelWithAlias):
    """The capability manifest (ai-catalog.json) hosted by publishers."""
    specVersion: str
    host: HostInfo | None = None  # Optional in core schema
    entries: List[CatalogEntry] = Field(default_factory=list)
    collections: List[CatalogCollection] | None = None


class QueryModel(BaseModelWithAlias):
    """Shared semantic and structural query object for POST /search and POST /explore."""
    text: str  # Required in OpenAPI QueryModel
    filter_: Dict[str, List[str]] | None = Field(default=None, alias="filter")

    @model_validator(mode="before")
    @classmethod
    def coerce_filter_scalars(cls, data: Any) -> Any:
        if isinstance(data, dict):
            filter_data = data.get("filter") or data.get("filter_")
            if isinstance(filter_data, dict):
                coerced = {}
                for k, v in filter_data.items():
                    if v is None:
                        coerced[k] = []
                    elif isinstance(v, list):
                        res = []
                        for x in v:
                            if x is None:
                                continue
                            if isinstance(x, bool):
                                res.append("true" if x else "false")
                            else:
                                res.append(str(x))
                        coerced[k] = res
                    elif isinstance(v, bool):
                        coerced[k] = ["true" if v else "false"]
                    else:
                        coerced[k] = [str(v)]
                # Put it back in the dictionary
                if "filter" in data:
                    data["filter"] = coerced
                else:
                    data["filter_"] = coerced
        return data


class SearchRequest(BaseModelWithAlias):
    """Payload for search POST request."""
    query: QueryModel
    federation: Literal["auto", "referrals", "none"] = "auto"
    pageSize: int = 10
    pageToken: str | None = None


class SearchResult(CatalogEntry):
    """A CatalogEntry with added search registry fields: score and source."""
    score: int = Field(ge=0, le=100)  # Required in OpenAPI SearchResultItem
    source: str  # Required in OpenAPI SearchResultItem


class RegistryReferral(BaseModelWithAlias):
    """Workload pointer recommendation details for federated upstream registries."""
    identifier: str
    displayName: str
    type_: Literal["application/ai-registry", "application/ai-registry+json"] | str = Field(alias="type")
    url: str


class SearchResponse(BaseModelWithAlias):
    """Payload for search response."""
    results: List[SearchResult]
    referrals: List[RegistryReferral] | None = None
    pageToken: str | None = None


# Explore API Definitions

class ExploreFacetRequest(BaseModelWithAlias):
    """Configures aggregation parameters for a single facet path."""
    field: str
    limit: int = 20
    minCount: int = 1


class ExploreResultType(BaseModelWithAlias):
    """Configures the facets to compute in an Explore request."""
    facets: List[ExploreFacetRequest]


class ExploreRequest(BaseModelWithAlias):
    """Payload for POST /explore request."""
    query: QueryModel | None = None
    resultType: ExploreResultType


class ExploreFacetBucket(BaseModelWithAlias):
    """A single bucket in a facet aggregation containing a value and match count."""
    value: str
    count: int


class ExploreFacetResult(BaseModelWithAlias):
    """Contains the list of facet buckets and other counts for a specific aggregated path."""
    buckets: List[ExploreFacetBucket]
    otherCount: int | None = None


class ExploreResponse(BaseModelWithAlias):
    """Payload for Explore response."""
    resultType: Literal["facets"] = "facets"
    facets: Dict[str, ExploreFacetResult]


class ListResponse(BaseModelWithAlias):
    """Payload for deterministic browsing list response."""
    items: List[CatalogEntry]
    total: int | None = None
    pageToken: str | None = None


class Error(BaseModelWithAlias):
    """Standard error object returned by the Registry API."""
    errorCode: str
    message: str
