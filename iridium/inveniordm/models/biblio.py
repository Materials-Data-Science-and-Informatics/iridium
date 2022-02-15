"""
Models for bibliographic metadata stored in an Invenio RDM record.

Based on Invenio RDM documentation and source.
https://github.com/inveniosoftware/invenio-rdm-records/blob/master/invenio_rdm_records/services/schemas/metadata.py
"""
from datetime import date
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import AnyHttpUrl, Field, root_validator
from typing_extensions import Annotated

from .base import JSONModel

edtf_date = Union[date, Annotated[str, Field(regex="^\\d{4}(-\\d{2})?$")]]
"""Date as ISO date or yyyy-mm or just yyyy."""


class Identifier(JSONModel):
    # TODO: record_identifiers_schemes+IdentifierSchema
    scheme: str
    identifier: str


class VocabularyRef(JSONModel):
    id: str
    # title: Optional[Dict[str, str]]  # dump_only


class PersonOrOrgType(str, Enum):
    PERSONAL = "personal"
    ORGANIZATIONAL = "organizational"


class PersonOrOrg(JSONModel):
    type: PersonOrOrgType
    name: Optional[str]
    given_name: Optional[str]
    family_name: Optional[str]
    identifiers: Optional[List[Identifier]]

    def __setattr__(self, key, value):
        if type == PersonOrOrgType.ORGANIZATIONAL:
            if key in ["given_name", "family_name"]:
                raise ValueError(f"An organization does not have {key}")
        else:
            if key in ["given_name", "family_name"]:
                super().__setattr__(key, value)
                super().__setattr__("name", f"{self.family_name}, {self.given_name}")
                return
            elif key == "name":
                raise AttributeError(
                    "Cannot set name directly! Use 'given_name' and 'family_name'!"
                )
        super().__setattr__(key, value)

    @root_validator
    def validate_names(cls, values):
        if "type" not in values:
            raise ValueError("type must be provided (personal or organizational)")

        if values["type"] == PersonOrOrgType.PERSONAL:
            if "given_name" not in values:
                raise ValueError("Family name of person must be provided")
            names = [values.get("family_name"), values.get("given_name")]
            values["name"] = ", ".join([n for n in names if n])

        elif values["type"] == PersonOrOrgType.ORGANIZATIONAL:
            if "name" not in values:
                raise ValueError("Name of organization must be provided")
            if "family_name" in values:
                del values["family_name"]
            if "given_name" in values:
                del values["given_name"]

        return values


class Affiliation(JSONModel):
    id: Optional[str]
    name: Optional[str]

    @root_validator
    def require_id_or_name(cls, values):
        has_id = "id" in values or values["id"]
        has_name = "name" in values or values["name"]
        if not has_id and not has_name:
            raise ValueError("Affiliation needs an id or a free-text name")
        return values


class CreatorRole(VocabularyRef):
    pass


class Creator(JSONModel):
    person_or_org: PersonOrOrg
    role: Optional[CreatorRole]
    affiliations: Optional[List[Affiliation]]


class Contributor(JSONModel):
    person_or_org: PersonOrOrg
    role: VocabularyRef
    affiliations: Optional[List[Affiliation]]


class Title(JSONModel):
    title: Annotated[str, Field(min_length=3)]
    type: VocabularyRef
    lang: Optional[VocabularyRef]


class Description(JSONModel):
    description: Annotated[str, Field(min_length=3)]
    type: VocabularyRef
    lang: Optional[VocabularyRef]


class Subject(JSONModel):
    id: Optional[str]
    subject: Optional[str]
    scheme: Optional[str]

    @root_validator
    def validate_subject(cls, values):
        has_id = "id" in values and values["id"]
        has_subj = "subject" in values and values["subject"]
        if has_id and has_subj:
            del values["subject"]
        if not has_id and not has_subj:
            raise ValueError("Subject needs an id or a free-text subject")
        return values


class RecordDate(JSONModel):
    date: edtf_date
    type: VocabularyRef
    description: Optional[str]


class RelatedIdentifier(JSONModel):
    # TODO: check record_identifiers_schemes
    relation_type: VocabularyRef
    resource_type: Optional[VocabularyRef]


class Funder(JSONModel):
    name: Annotated[str, Field(min_length=1)]
    scheme: str
    identifier: str


class Award(JSONModel):
    title: Annotated[str, Field(min_length=1)]
    number: Annotated[str, Field(min_length=1)]
    scheme: Optional[str]
    identifie: Optional[str]


class Funding(JSONModel):
    funder: Funder
    award: Award

    @root_validator
    def require_funder_or_award(cls, values):
        has_funder = "funder" in values and values["funder"]
        has_award = "award" in values and values["award"]
        if not has_funder and not has_award:
            raise ValueError("Funding needs a funder or an award")
        return values


class Reference(JSONModel):
    # TODO: check record_references_schemes
    reference: str


class Props(JSONModel):
    url: AnyHttpUrl
    scheme: str


class Rights(JSONModel):
    id: str

    # in practice, some API endpoints return these,
    # while some (like the "draft from record" method) do not :/
    title: Optional[Dict[str, str]]
    description: Optional[Dict[str, str]]
    props: Optional[Props]
    # link = Optional[AnyHttpUrl]


class Location(JSONModel):

    geometry: Dict[str, Any]  # TODO: GeometryObjectSchema
    place: Optional[str]
    identifiers: Optional[List[Identifier]]
    description: str

    @root_validator
    def validate_values(cls, values):
        """Validate identifier based on type."""
        if (
            not values.get("geometry")
            and not values.get("place")
            and not values.get("identifiers")
            and not values.get("description")
        ):
            raise ValueError(
                "At least one of ['geometry', 'place', 'identifiers', 'description'] must be present."
            )


class Feature(JSONModel):
    features: List[Location]


class BibMetadata(JSONModel):
    # these are not optional in records, but can be optional in drafts
    resource_type: Optional[VocabularyRef]
    creators: Optional[Annotated[List[Creator], Field(min_items=1)]]
    title: Optional[Annotated[str, Field(min_length=3)]]
    publication_date: Optional[edtf_date]

    additional_titles: Optional[List[Title]]
    publisher: Optional[str]
    subjects: Optional[List[Subject]]
    contributors: Optional[List[Contributor]]
    dates: Optional[List[RecordDate]]
    languages: Optional[List[VocabularyRef]]
    identifiers: Optional[List[Identifier]]
    related_identifiers: Optional[List[RelatedIdentifier]]
    sizes: Optional[List[Annotated[str, Field(min_length=1)]]]
    formats: Optional[List[Annotated[str, Field(min_length=1)]]]
    version: Optional[str]
    rights: Optional[List[Rights]]
    description: Annotated[Optional[str], Field(min_length=3)]
    additional_descriptions: Optional[List[Description]]
    locations: Optional[Feature]
    funding: Optional[List[Funding]]
    references: Optional[List[Reference]]
