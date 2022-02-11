"""Convenience wrapper for draft and record API."""
from __future__ import annotations

from datetime import datetime
from typing import BinaryIO, Dict, Iterable, Optional, Tuple

from .generic import AccessProxy, Query
from .inveniordm.api import InvenioRDMClient
from .inveniordm.models import (
    AccessLink,
    FileMetadata,
    Files,
    LinkPermission,
    Record,
    Results,
)
from .pprint import NoPrint, PrettyRepr


class WrappedRecord:
    """
    Class that wraps the raw data and the low-level REST API into something convenient.

    It can be used to perform all operations that are possible on individual records.

    Conceptually, there is a distinction between records and drafts.
    Practically, it seems difficult to model this in a static way.
    Therefore, this class covers both kinds of entities and determines
    the allowed methods through runtime inspection.

    The `access_links` and `files` attributes expose special interfaces with
    immediate synchronization with the server.

    Changes to the `metadata` and `access` attributes are synchronized only
    on `save()` or `publish()`.

    All other attributes are to be considered read-only,
    overwriting them will have no effect on the actual data on the server.
    """

    __slots__ = ["_client", "_record", "_is_draft", "_access_links", "_files"]

    def __init__(self, cl: InvenioRDMClient, rec: Record, is_draft: bool):
        self._client: InvenioRDMClient = cl
        self._record: Record = rec

        # there is no such "field" in Invenio RDM, these are really 2 APIs!
        # so we track the difference on our own.
        #
        # Also, this must come BEFORE initializing files,
        # as `WrappedFiles` accesses the property is_draft,
        # which only works correctly once `_is_draft` is set.
        self._is_draft: bool = is_draft

        self._files: WrappedFiles = WrappedFiles(self)
        self._access_links: AccessLinks = AccessLinks(self)

    @property
    def files(self):
        """Return interface for managing files in this record."""
        return self._files

    @property
    def access_links(self):
        """Return interface for managing access links for this record."""
        self._expect_published()
        return self._access_links

    @property
    def is_draft(self):
        """
        Return whether the current object is an editable draft of a record.

        Only drafts can be saved, published or deleted.
        """
        return self._is_draft

    def _expect_draft(self):
        if not self.is_draft:
            raise TypeError("Operation supported only for drafts!")

    def _expect_published(self):
        if self.is_draft or not self.is_published:
            raise TypeError("Operation supported only for published records!")

    def is_saved(self):
        """
        Check whether the current draft is in sync with the draft on in Invenio RDM.

        This means that they must agree on access, metadata and files attributes,
        as these are the ones modifiable by the user.
        """
        self._expect_draft()

        # need to "wrap" to initialize e.g. the 'files' part correctly
        drft = WrappedRecord(
            self._client, self._client.draft.get(self._record.id), True
        )

        # TODO: track https://github.com/inveniosoftware/invenio-app-rdm/issues/1233
        # for now, workaround: ignore access.status:
        drft.access.status = self._record.access.status

        # compare relevant contents
        same_access = drft.access == self._record.access
        same_metadata = drft.metadata == self._record.metadata
        same_files = drft.files._files == self.files._files  # compare unwrapped
        return same_access and same_metadata and same_files

    def edit(self) -> WrappedRecord:
        """
        Create or switch to an existing draft based on the current record version.

        This draft can be used to update the metadata of the published record version.
        For this, change metadata accordingly and call `save()` and/or `publish()`.

        This object will stay a draft until `publish()` is called.
        To get back from the draft to the original record, without publishing,
        just request it again from the repository.

        The method returns this object itself for convenience, e.g. to write:
        `draft = rdm.records["REC_ID"].edit()`
        which is equivalent to:
        `draft = rdm.drafts.create("REC_ID", new_version=False)`
        """
        self._expect_published()

        self._record = self._client.draft.from_record(self._record.id)
        self._is_draft = True
        return self

    def new_version(self) -> WrappedRecord:
        """
        Create or switch to an existing draft for a new version of the current record.

        This works like `edit()`, with the difference that in a new version
        it is possible to change the files as well, not only metadata.

        The method returns this object itself for convenience, e.g. to write:
        `draft = rdm.records["REC_ID"].new_version()`
        which is equivalent to:
        `draft = rdm.drafts.create("REC_ID")`
        """
        self._expect_published()

        self._record = self._client.draft.new_version(self._record.id)
        self._is_draft = True  # must be set before loading files for correct behavior
        self._files = WrappedFiles(self)  # update files information
        return self

    def save(self):
        """
        Save changes to draft record.

        This commits the changes to this draft object to the Invenio RDM instance.
        Returns dict with validation errors from the server.

        Notice that if the draft belongs to a published record version,
        this will only affect the draft (i.e. the version accessed via `edit()`).
        The changes will only be visible to others after calling `publish()`.
        """
        self._expect_draft()

        self._record = self._client.draft.update(self._record)

        # present validation errors
        errs: Optional[Dict[str, str]] = None
        if self._record.errors is not None:
            errs = {e.field: " ".join(e.messages) for e in self._record.errors}
            self._record.errors = None  # no need to keep them
        # don't need to wrap None for printing... would print 'None'
        return PrettyRepr(errs) if errs else None

    def publish(self):
        """
        Save and publish the draft as the actual record.

        Notice that:
        * a published record cannot be deleted and its files cannot be modified
        * you can only change metadata of the record for that version (with `edit()`)
        * to also replace files, you must create a new version (with `new_version()`)
        """
        self._expect_draft()

        # in case there were still unsaved changes, save. check for validation errors
        # (server validation also checks that files are attached when enabled)
        errors = self.save()
        if errors is not None and len(errors) > 0:
            raise ValueError(
                "There were validation errors on save, cannot publish:\n"
                f"{repr(errors)}"
            )

        self._record = self._client.draft.publish(self._record.id)
        self._is_draft = False

    def delete(self):
        """
        Delete this draft record.

        After deletion, this object is not backed by a draft in Invenio RDM.
        Therefore, all method calls and attribute accesses will be invalid.
        """
        self._expect_draft()

        self._client.draft.delete(self._record.id)
        # to prevent the user from doing anything stupid, make it fail
        self._record = None  # type: ignore
        self._access_links = None  # type: ignore

    # NOTE: the following is a really, really bad idea!
    # While it would be cool to write `del record_object`, this
    # would kill the draft whenever the GC will clean up unused objects!
    # So DON'T do this. I left this as a friendly reminder that I naively tried this.
    # def __del__(self):
    #     self.delete()

    # proxy through all remaining methods to the raw record
    def __getattr__(self, name: str):
        return self._record.__getattribute__(name)

    def __setattr__(self, name: str, value):
        if name in ["metadata", "access"]:  # the only usefully writable record fields
            return self._record.__setattr__(name, value)
        elif name in self.__slots__:  # private, local attribute
            super().__setattr__(name, value)
        else:
            raise ValueError(f"Attribute {name} is read-only!")

    # magic methods must be proxied by hand
    def __repr__(self):
        patch = {"files": list(self.files.keys())}
        return repr(PrettyRepr(self._record.copy(exclude={"links"}, update=patch)))

    # help the shell to list what's there
    def __dir__(self):
        return super().__dir__()


# ---- access link API wrappers ----


class WrappedAccessLink:
    """
    High-level wrapper for managing an access link.

    All that can be done is inspecting it, destroying it and modifying
    the fields `expires_at` and `permission`. The other fields are read-only.

    Changes performed through this interface are synchronized with the server immediately.
    """

    # TODO: the access link is not containing any concrete URL!
    # there should be a property that constructs the correct URL with the shape:
    # https://INVENIORDM_BASE/records/REC_ID?token=TOKEN[&preview=1 if preview mode]
    # (based on the links generated in the Invenio RDM Web UI)

    # TODO: how to access a private record through an access link shared by someone else?
    # probably need to access the URL for the token to be added to the user identity

    def __init__(self, parent: WrappedRecord, lnk: AccessLink):
        self._parent: WrappedRecord = parent
        self._link: AccessLink = lnk

    @property
    def expires_at(self) -> Optional[datetime]:
        self._check_deleted()
        return self._link.expires_at

    @expires_at.setter
    def expires_at(self, value: Optional[datetime]):
        self._check_deleted()
        self._link.expires_at = value
        self._parent._client.record.access_links.update(self._parent.id, self._link)

    @property
    def permission(self) -> Optional[LinkPermission]:
        self._check_deleted()
        return self._link.permission

    @permission.setter
    def permission(self, value: Optional[LinkPermission]):
        self._check_deleted()
        self._link.permission = value
        self._parent._client.record.access_links.update(self._parent.id, self._link)

    @property
    def id(self) -> Optional[str]:
        self._check_deleted()
        return self._link.id

    @property
    def token(self) -> Optional[str]:
        self._check_deleted()
        return self._link.token

    @property
    def created_at(self) -> Optional[datetime]:
        self._check_deleted()
        return self._link.created_at

    def delete(self):
        """Delete the underlying access link."""
        self._parent._client.record.access_links.delete(self._parent.id, self._link.id)
        self._link = None  # type: ignore

    def _check_deleted(self):
        if self._link is None:
            raise ValueError("Invalid access link! Maybe you deleted it?")

    # magic methods must be proxied by hand
    def __repr__(self):
        return repr(self._link)


class AccessLinkQuery(Query):
    def __init__(self, rec: WrappedRecord):
        super().__init__()
        self._client: InvenioRDMClient = rec._client
        self._parent: WrappedRecord = rec

    def _query_items(self, **kwargs) -> Results:
        # access links are special, so here we ignore the passed kwargs, because
        # they take no query parameters. yet, the interface requires accepting them
        ret = self._client.record.access_links.list(self._parent.id)
        ret.hits.hits = [WrappedAccessLink(self._parent, x) for x in ret.hits.hits]
        return ret


class AccessLinks(AccessProxy):
    """Sub-interface for interaction with access links."""

    def __init__(self, parent: WrappedRecord):
        self._client: InvenioRDMClient = parent._client
        self._parent: WrappedRecord = parent

    def _get_query(self, **kwargs) -> Query:
        return AccessLinkQuery(self._parent)

    def _get_entity(self, link_id: str):
        lnk = self._client.record.access_links.get(self._parent.id, link_id)
        return WrappedAccessLink(self._parent, lnk)

    def create(
        self,
        expires_at: Optional[datetime] = None,
        permission: Optional[LinkPermission] = None,
    ):
        """Create an access link for the record that can be shared."""
        lnk = self._client.record.access_links.create(
            self._parent.id, expires_at, permission
        )
        return WrappedAccessLink(self._parent, lnk)


# ---- file API wrappers ----


class WrappedFiles:
    """
    Dict-like interface for interaction with files.

    Changes performed through this interface are synchronized with the server immediately.
    """

    def __init__(self, parent: WrappedRecord):
        self._parent: WrappedRecord = parent
        self._client: InvenioRDMClient = parent._client

        # _files should contain the raw structure as returned by the API,
        # But this is only accessible if file support is enabled for the record.
        self._files: Files = parent._record.files  # stub with just "enabled" state
        if parent._record.files.enabled:
            self._files = self._get_fileinfos()

    def _get_fileinfos(self) -> Files:
        if self._parent.is_draft:
            return self._client.draft.files(self._parent.id)
        else:
            return self._client.record.files(self._parent.id)

    @property
    def enabled(self) -> bool:
        return self._files.enabled

    @enabled.setter
    def enabled(self, value: bool):
        if self._files.entries is not None and len(self._files.entries) > 0:
            raise ValueError("This value can only be modified if there are no files!")

        # set files.enabled state on server without committing other record changes
        rec = self._client.draft.get(self._parent.id)
        rec.files.enabled = value
        self._client.draft.update(rec)
        # if no exception happened, update the values locally
        self._parent._record.files.enabled = value
        self._files.enabled = value
        if self._files.enabled and self._files.entries is None:
            self._files.entries = []

    def _check_mutable(self):
        if not self._parent.is_draft or self._parent.is_published:
            raise ValueError("Operation only supported on new record (version) drafts!")

    def _check_enabled(self):
        if not self._files.enabled:
            raise ValueError("Operation only supported if files are enabled!")

    def _check_filename(self, filename, should_exist: bool = True):
        """Complain if file does (not) exist."""
        if should_exist and filename not in self._entries_dict():
            raise ValueError(f"No such file in record: {filename}")
        if not should_exist and filename in self._entries_dict():
            raise ValueError(f"File with this name already in record: {filename}")

    def download(self, filename: str) -> BinaryIO:
        """Download file from record or draft."""
        self._check_enabled()
        self._check_filename(filename)

        if self._parent.is_draft:
            return self._client.draft.file_download(self._parent.id, filename)
        else:
            return self._client.record.file_download(self._parent.id, filename)

    def delete(self, filename: str):
        """Delete file from record draft."""
        self._check_mutable()
        self._check_filename(filename)

        self._client.draft.file_delete(self._parent.id, filename)
        # if no exception happened, it worked ->
        # remove the entry locally (thereby avoid reloading data)
        assert self._files.entries is not None
        self._files.entries = [fm for fm in self._files.entries if fm.key != filename]

    def import_old(self):
        """Import files from the previous version."""
        self._check_mutable()
        self._check_enabled()
        if self._parent.versions.index < 2:
            raise ValueError("Cannot import files, this is the first record version!")
        if self._files.entries is not None and len(self._files.entries) > 0:
            raise ValueError("Can only import if no new files were uploaded yet!")

        self._files = self._client.draft.files_import(self._parent.id)

    def upload(self, filename: str, data: BinaryIO):
        """
        Upload a file.

        Takes a binary stream as input, you have to `open` your file yourself with `"rb"`.
        """
        self._check_mutable()
        self._check_enabled()
        self._check_filename(filename, False)

        self._client.draft.file_upload_start(self._parent.id, filename)
        self._client.draft.file_upload_content(self._parent.id, filename, data)
        self._client.draft.file_upload_complete(self._parent.id, filename)
        self._files = self._get_fileinfos()

    # ---- dict-like behaviour to access file metadata ----

    def _entries_dict(self):
        """Exposes file entries as delivered by backend into a dict."""
        # There should not be a bazillion files per record,
        # so recreating the dict on access should be no problem at all.
        # When need arises, we can switch to something more efficient.
        if not self.enabled or not self._files.entries:
            return {}  # there is no 'entries' key if files are disabled
        assert self._files.entries is not None  # if enabled, must be present
        return {fileinfo.key: fileinfo for fileinfo in self._files.entries}

    def keys(self) -> Iterable[str]:
        return self._entries_dict().keys()

    def values(self) -> Iterable[FileMetadata]:
        return self._entries_dict().values()

    def items(self) -> Iterable[Tuple[str, FileMetadata]]:
        return self._entries_dict().items()

    def __iter__(self) -> Iterable[str]:
        return iter(self._entries_dict())

    def __len__(self) -> int:
        return len(self._entries_dict())

    def __getitem__(self, filename) -> FileMetadata:
        return self._entries_dict()[filename]

    def __repr__(self) -> str:
        # there is too much information in the metadata anyway, just show names
        # and indicate dict-like accessibility
        return repr({k: NoPrint(v) for k, v in self._entries_dict().items()})
