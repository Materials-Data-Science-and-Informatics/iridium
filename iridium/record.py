"""Convenience wrapper for draft and record API."""

from datetime import datetime
from typing import Optional

from .generic import AccessProxy, Query
from .inveniordm.api import InvenioRDMClient
from .inveniordm.models import AccessLink, LinkPermission, Record, Results

# TODO: how to access a private record through an access link shared by someone else?


class WrappedRecord:
    """
    Class that wraps the raw data and the low-level REST API into something convenient.

    It can be used to perform all operations that are possible on individual records.

    Conceptually, there is a distinction between records and drafts.
    Practically, it seems difficult to model this in a static way.
    Therefore, this class covers both kinds of entities and determines
    the allowed methods through runtime inspection.
    """

    def __init__(self, cl: InvenioRDMClient, rec: Record, is_draft: bool):
        self._client = cl
        self._record = rec
        self._access_links = AccessLinks(self)
        self._is_draft = is_draft  # there is no such "field", these are really 2 APIs!
        self.files  # force to load the file metadata

    @property
    def is_draft(self):
        """
        Return whether the current object is an editable draft of a record.

        Only drafts can be saved, published or deleted.
        """
        return self._is_draft

    @property
    def is_published(self):
        """
        Return whether the current object represents an already published record.

        Files can only be modified for unpublished records.
        """
        return self._record.is_published

    @property
    def access_links(self):
        """Return interface for managing access links for this record."""
        if self.is_draft or not self.is_published:
            raise TypeError("Operation supported only for published records!")
        return self._access_links

    @property
    def files(self):
        """Return metadata associated with files in the record."""
        # if there is an "entries" key, we already have more than the stub
        if self._record.files.entries:
            return self._record.files
        # otherwise no cached data is available -> load
        if self.is_draft:
            ret = self._client.draft.files(self._record.id)
        else:
            ret = self._client.record.files(self._record.id)
        self._record.files = ret
        return ret

    def edit(self):
        """
        Create or switch to an existing draft based on the current record version.

        This draft can be used to update the metadata of the published record version.
        For this, change metadata accordingly and call `save()` and `publish()`.
        """
        if self.is_draft or not self.is_published:
            raise TypeError("Operation supported only for published records!")

        self._record = self._client.draft.from_record(self._record.id)
        self._is_draft = True

    def new_version(self):
        """
        Create or switch to an existing draft for a new version of the current record.

        This works like `edit()`, with the difference that in a new version
        it is possible to change the files as well, not only metadata.
        """
        if self.is_draft or not self.is_published:
            raise TypeError("Operation supported only for published records!")

        self._record = self._client.draft.new_version(self._record.id)
        self._is_draft = True

    def save(self):
        """
        Save changes to draft record.

        This commits the changes to this draft object to the Invenio RDM instance.

        Notice that if the draft belongs to a published record version,
        this will only affect the draft (i.e. the version accessed via `edit()`).
        The changes will only be visible to others after calling `publish()`.
        """
        if not self.is_draft:
            raise TypeError("Operation supported only for drafts!")

        self._record = self._client.draft.update(self._record)

    def publish(self):
        """
        Publish the draft as the actual record.

        Notice that:
        * a published record cannot be deleted
        * you can only change metadata of the record for that version (with `edit()`)
        * to also change files, you must create a new version (with `new_version()`)
        """
        if not self.is_draft:
            raise TypeError("Operation supported only for drafts!")

        self._record = self._client.draft.publish(self._record.id)
        self._is_draft = False

    def delete(self):
        """
        Delete this draft record.

        After deletion, this object is not backed by a draft in Invenio RDM.
        Therefore, all method calls will result in errors.
        """
        if not self.is_draft:
            raise TypeError("Operation supported only for drafts!")

        self._client.draft.delete(self._record.id)
        self._is_draft = False  # to prevent attempts to save() or publish()

    # NOTE: the following is really, really bad idea!
    # While it would be cool to write `del record_object`, this
    # would kill the draft whenever the GC will clean up unused objects!
    # So DON'T do this. I left this as a friendly reminder that I naively tried this.
    # def __del__(self):
    #     self.delete()

    # proxy through all remaining methods to the raw record
    def __getattr__(self, name: str):
        return self._record.__getattribute__(name)

    # magic methods must be proxied by hand
    def __str__(self):
        return str(self._record)


# ---- access link API wrappers ----


class WrappedAccessLink:
    """
    High-level wrapper for managing an access link.

    All that can be done is inspecting it, destroying it and modifying
    the fields `expires_at` and `permission`. The other fields are read-only.
    """

    # TODO: the access link is not containing any concrete URL!
    # there should be a property that constructs the correct URL with the shape:
    # https://INVENIORDM_BASE/records/REC_ID?token=TOKEN[&preview=1 if preview mode]
    # (based on the links generated in the Invenio RDM Web UI)

    def __init__(self, rec: WrappedRecord, lnk: AccessLink):
        self._record = rec
        self._link: AccessLink = lnk

    @property
    def expires_at(self) -> Optional[datetime]:
        self.check_deleted()
        return self._link.expires_at

    @expires_at.setter
    def expires_at(self, value: Optional[datetime]):
        self.check_deleted()
        self._link.expires_at = value
        self._record._client.record.access_links.update(self._record.id, self._link)

    @property
    def permission(self) -> Optional[LinkPermission]:
        self.check_deleted()
        return self._link.permission

    @permission.setter
    def permission(self, value: Optional[LinkPermission]):
        self.check_deleted()
        self._link.permission = value
        self._record._client.record.access_links.update(self._record.id, self._link)

    @property
    def id(self) -> Optional[str]:
        self.check_deleted()
        return self._link.id

    @property
    def token(self) -> Optional[str]:
        self.check_deleted()
        return self._link.token

    @property
    def created_at(self) -> Optional[datetime]:
        self.check_deleted()
        return self._link.created_at

    def delete(self):
        """Delete the underlying access link."""
        self._record._client.record.access_links.delete(self._record.id, self._link.id)
        self._link = None  # type: ignore

    def check_deleted(self):
        if self._link is None:
            raise ValueError("Invalid access link! Maybe you deleted it?")

    # magic methods must be proxied by hand
    def __str__(self):
        return str(self._link)


class AccessLinkQuery(Query):
    def __init__(self, rec: WrappedRecord):
        super().__init__()
        self._client = rec._client
        self._record = rec

    def _query_items(self, **kwargs) -> Results:
        # access links are special, so here we ignore the passed kwargs, because
        # they take no query parameters. yet, the interface requires accepting them
        ret = self._client.record.access_links.list(self._record.id)
        ret.hits.hits = list(
            map(lambda x: WrappedAccessLink(self._record, x), ret.hits.hits)
        )
        return ret


class AccessLinks(AccessProxy):
    """Sub-interface for interaction with access links."""

    def __init__(self, rec: WrappedRecord):
        self._client = rec._client
        self._record = rec

    def _get_query(self, **kwargs) -> Query:
        return AccessLinkQuery(self._record)

    def _get_entity(self, link_id: str):
        lnk = self._client.record.access_links.get(self._record.id, link_id)
        return WrappedAccessLink(self._record, lnk)

    def create(
        self,
        expires_at: Optional[datetime] = None,
        permission: Optional[LinkPermission] = None,
    ):
        """Create an access link for the record that can be shared."""
        lnk = self._client.record.access_links.create(
            self._record.id, expires_at, permission
        )
        return WrappedAccessLink(self._record, lnk)


# ---- file API wrappers ----


class WrappedFiles:
    """Sub-interface for interaction with files."""

    pass
