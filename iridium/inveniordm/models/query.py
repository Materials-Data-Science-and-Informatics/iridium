"""ElasticSearch query related models for records and vocabularies."""
from enum import Enum
from typing import Dict, Generic, List, Optional, Set, Type, TypeVar

from pydantic import AnyHttpUrl, BaseModel, Extra, Field
from typing_extensions import Annotated

from .base import JSONModel
from .technical import Entity

# ---- ELASTICSEARCH QUERIES ----


class QueryArgs(BaseModel):
    """
    Query parameters for ElasticSearch queries.

    https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#search-records
    """

    class Config:
        extra = Extra.forbid

    q: Optional[str]
    size: Optional[int]
    page: Optional[int]

    # sorting depends on the kind of query and the kind of objects
    # so we keep this untyped for simplicities sake.
    #
    # SortOrder enum contains the user-selectable sort orders.
    #
    # vocabularies have their own default sort orders:
    #   languages, licenses and resource_types are sorted by "title"
    #   affiliations are sorted by "name", subjects by "subject"
    # this cannot be modified in the vocabulary query, though.
    sort: Optional[str]

    def __str__(self):
        """Assemble query parameter string to add to URL (without the leading '?')."""
        nonempty_lists = {
            k
            for k in self.__dict__.keys()
            if isinstance(self.__dict__[k], list) and len(self.__dict__[k]) > 0
        }
        lists = [f"{k}={v}" for k in nonempty_lists for v in self.__dict__[k]]
        singl = [
            f"{k}={self.__dict__[k]}"
            for k in self.__dict__
            if self.__dict__[k] is not None and k not in nonempty_lists
        ]
        return "&".join(singl + lists)


class AccessStatus(str, Enum):
    open = "open"
    metadata_only = "metadata-only"
    embargoed = "embargoed"


class RecQueryArgs(QueryArgs):
    """https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#search-records"""

    allversions: Optional[bool]

    # these are used in the web ui, no documentation:
    access_status: Optional[List[AccessStatus]]
    resource_type: Optional[List[str]]


class VocQueryArgs(QueryArgs):
    """https://inveniordm.docs.cern.ch/reference/rest_api_vocabularies/#search-vocabularies"""

    tags: Optional[str]
    suggest: Optional[str]


class SortOrder(str, Enum):
    """Sort orders supported for presenting query results (based on UI)."""

    # for all records
    best_match = "bestmatch"
    newest = "newest"
    oldest = "oldest"
    version = "version"

    # for user records only
    updated_asc = "updated-asc"
    updated_desc = "updated-desc"


class VocType(str, Enum):
    """Vocabulary types available for query in Invenio RDM API."""

    languages = "languages"
    licenses = "licenses"
    resource_types = "resourcetypes"
    # special:
    affiliations = "affiliations"
    subjects = "subjects"


_special_voc: Set[VocType] = {VocType.affiliations, VocType.subjects}
"""Default special vocabulary types with distinct API endpoints."""


def voc_special(voc: VocType) -> bool:
    """Return True if vocabulary type needs special result parsing."""
    return voc in _special_voc


# ---- ELASTICSEARCH QUERY RESULTS ----

T = TypeVar("T")


class ResultPage(JSONModel, Generic[T]):
    """Sub-object containing the actual results."""

    hits: List[T]
    total: int


class Results(JSONModel, Generic[T]):
    """JSON returned by ElasticSearch."""

    hits: ResultPage[T]

    # not included for access_links queries, otherwise present
    links: Optional[Dict[str, AnyHttpUrl]]
    sortBy: Optional[str]

    def parse_hits(self, obj_cls: Type[T]):
        """Try to parse the query hits into the provided model class."""
        self.hits.hits = [obj_cls.parse_obj(x) for x in self.hits.hits]  # type: ignore


# ---- VOCABULARY SPECIFIC ----

i18n_str = Annotated[str, Field(regex="^[a-z]{2}$")]


class VocTerm(Entity):
    """Term of a regular vocabulary."""

    class Config:
        extra = Extra.forbid

    title: Dict[i18n_str, str]
    description: Optional[Dict[i18n_str, str]]
    icon: Optional[str]

    type: str
    props: Dict[str, str]
    tags: List[str]


class VocSubject(Entity):
    class Config:
        extra = Extra.forbid

    scheme: str
    subject: str


class VocAffIdentifier(JSONModel):
    class Config:
        extra = Extra.forbid

    scheme: str
    identifier: str


class VocAffiliation(Entity):
    class Config:
        extra = Extra.forbid

    title: Dict[i18n_str, str]
    name: str
    acronym: Optional[str]
    identifiers: List[VocAffIdentifier]


_voc_classes = {
    VocType.affiliations: VocAffiliation,
    VocType.subjects: VocSubject,
}
"""Mapping of special vocabulary types to the respective classes."""


def voc_class(voc: VocType):
    """Return correct class for parsing result of vocabulary query."""
    return _voc_classes.get(voc, VocTerm)
