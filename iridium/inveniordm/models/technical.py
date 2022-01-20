"""Models for Invenio RDM specific, technical metadata."""
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import AnyHttpUrl, Extra, Field, root_validator
from typing_extensions import Annotated

from .base import JSONModel
from .biblio import BibMetadata


class Agent(JSONModel):
    """
    https://github.com/inveniosoftware/invenio-rdm-records/blob/master/invenio_rdm_records/services/schemas/parent/access.py#L44
    """

    user: int


class Grant(JSONModel):
    """
    https://github.com/inveniosoftware/invenio-rdm-records/blob/master/invenio_rdm_records/services/schemas/parent/access.py#L22
    """

    subject: str
    id: str
    level: str


class LinkPermission(str, Enum):
    VIEW = "view"
    PREVIEW = "preview"
    EDIT = "edit"


class AccessLink(JSONModel):
    """
    https://github.com/inveniosoftware/invenio-rdm-records/blob/master/invenio_rdm_records/services/schemas/parent/access.py#L30
    """

    id: str  # dump_only
    created_at: Optional[datetime]
    expires_at: Optional[datetime]
    permission: Optional[LinkPermission]
    token: Optional[str]  # dump_only, empirically optional


class ParentAccess(JSONModel):
    """
    https://github.com/inveniosoftware/invenio-rdm-records/blob/master/invenio_rdm_records/services/schemas/parent/access.py#L50
    """

    owned_by: Annotated[List[Agent], Field(min_items=1)]
    grants: Optional[List[Grant]]
    links: Optional[List[AccessLink]]


class Communities(JSONModel):
    """
    https://github.com/inveniosoftware/invenio-rdm-records/blob/master/invenio_rdm_records/services/schemas/parent/communities.py#L13
    """

    # NOTE: communities object can be empty in practice!
    ids: Optional[List[str]]
    default: Optional[str]


class GenericRequest(JSONModel):
    """
    https://github.com/inveniosoftware/invenio-requests/blob/master/invenio_requests/services/schemas.py#L95
    https://github.com/inveniosoftware/invenio-requests/blob/master/invenio_requests/services/schemas.py#L68
    """

    created_by: Dict[str, str]
    receiver: Dict[str, str]
    topic: Dict[str, str]

    type: str
    title: Optional[str] = ""
    description: str
    number: str  # dump_only
    status: str  # dump_only
    is_closed: bool  # dump_only
    is_open: bool  # dump_only
    expires_at: datetime  # dump_only
    is_expired: bool  # dump_only


class Parent(JSONModel):
    """
    https://github.com/inveniosoftware/invenio-rdm-records/blob/master/invenio_rdm_records/services/schemas/parent/__init__.py#L20
    https://github.com/inveniosoftware/invenio-drafts-resources/blob/master/invenio_drafts_resources/services/records/schema.py#L24
    """

    id: str

    # NOTE: all of these can be missing in practice! empirically observed fact
    access: Optional[ParentAccess]  # dump_only
    review: Optional[GenericRequest]
    communities: Optional[Communities]  # dump_only


class SupportedPIDs(str, Enum):
    """
    https://github.com/inveniosoftware/invenio-rdm-records/blob/master/invenio_rdm_records/config.py#L464
    """

    DOI = "doi"
    OAI = "oai"


class ExternalPID(JSONModel):
    """
    https://github.com/inveniosoftware/invenio-rdm-records/blob/master/invenio_rdm_records/services/schemas/pids.py#L15
    """

    identifier: str
    provider: str
    client: Optional[str]


class AccessPolicy(str, Enum):
    PUBLIC = "public"
    RESTRICTED = "restricted"


class Embargo(JSONModel):
    """
    https://github.com/inveniosoftware/invenio-rdm-records/blob/master/invenio_rdm_records/services/schemas/access.py
    """

    active: bool
    until: Optional[date]
    reason: Optional[str]

    @root_validator
    def active_needs_until(cls, values):
        if values["active"] and ("until" not in values or not values["until"]):
            raise ValueError("'until' must be provided if embargo is 'active'")
        return values


class AccessControl(JSONModel):
    """
    https://github.com/inveniosoftware/invenio-rdm-records/blob/master/invenio_rdm_records/services/schemas/access.py#L54
    """

    record: AccessPolicy
    files: AccessPolicy
    embargo: Optional[Embargo]
    status: Optional[str]

    # TODO: only check on creating records.
    # for existing records it can be public + old embargo
    # @root_validator
    # def embargo_needs_restricted(cls, values):
    #     if "record" in values and values["record"] == AccessPolicy.RESTRICTED:
    #         return values
    #     if "files" in values and values["files"] == AccessPolicy.RESTRICTED:
    #         return values
    #     raise ValueError(
    #         "'embargo' assumes that the record or files are/were restricted"
    #     )


class FileMetadata(JSONModel):
    """
    https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#get-a-record-files-metadata
    """

    class Config:
        extra = Extra.forbid

    key: str
    created: datetime
    updated: datetime
    status: str

    # this one seems to be unused right now
    metadata: Optional[Dict[str, str]]

    checksum: Optional[str]
    mimetype: Optional[str]
    size: Optional[int]
    file_id: Optional[str]
    version_id: Optional[str]
    bucket_id: Optional[str]
    storage_class: Optional[str]

    links: Dict[str, AnyHttpUrl]  # dump_only


class Files(JSONModel):
    """
    https://github.com/inveniosoftware/invenio-rdm-records/blob/master/invenio_rdm_records/services/schemas/files.py#L39
    """

    enabled: bool
    default_preview: Optional[str]
    order: Optional[List[str]]
    entries: Optional[List[FileMetadata]]


class Versions(JSONModel):
    """
    https://github.com/inveniosoftware/invenio-rdm-records/blob/master/invenio_rdm_records/services/schemas/versions.py#L15
    https://github.com/inveniosoftware/invenio-drafts-resources/blob/master/invenio_drafts_resources/services/records/schema.py#L16
    """

    index: int
    is_latest: bool
    is_latest_draft: Optional[bool]


class Entity(JSONModel):
    """
    Abstracted entity for common properties of a vocabulary term and a record.

    https://github.com/inveniosoftware/invenio-records-resources/blob/master/invenio_records_resources/services/records/schema.py#L22
    """

    id: str
    created: datetime  # dump_only
    updated: datetime  # dump_only
    links: Dict[str, AnyHttpUrl]  # dump_only
    revision_id: int  # dump_only


class PIDs(JSONModel):
    __root__: Dict[SupportedPIDs, ExternalPID]


class Record(Entity):
    """
    This class represents both records and record drafts.

    Due to this fact it allows things that are allowed in drafts, but not in records.
    We rely on the validation of Invenio itself to complain about such things.

    https://github.com/inveniosoftware/invenio-rdm-records/blob/master/invenio_rdm_records/services/schemas/__init__.py#L34
    https://github.com/inveniosoftware/invenio-drafts-resources/blob/master/invenio_drafts_resources/services/records/schema.py#L30
    """

    class Config:
        extra = Extra.forbid

    # RecordSchema(overridden)
    parent: Parent
    versions: Versions  # dump_only
    is_published: bool  # dump_only

    # RDMRecordSchema
    pids: PIDs
    metadata: BibMetadata
    access: AccessControl
    files: Files

    # revision: int  # dump_only, seems to be unused

    expires_at: Optional[datetime]  # seems to be only used in drafts

    # this does not seem to be useful, should rather rely on own validation
    errors: Optional[Dict[str, Any]]  # seems to be only used in drafts


class Draft(Record):
    """A draft is just an unpublished record."""

    pass
