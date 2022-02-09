"""Convenience wrapper for draft and record API."""

from datetime import datetime
from typing import BinaryIO, Iterable, Optional, Tuple

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
from .pprint import NoPrint

# TODO: how to access a private record through an access link shared by someone else?
# probably need to access the URL for the token to be added to the user identity


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
        self._client: InvenioRDMClient = cl
        self._record: Record = rec

        # there is no such "field" in Invenio RDM, these are really 2 APIs!
        # so we track the difference on our own.
        #
        # Also, this must come BEFORE initializing files,
        # as `WrappedFiles` accesses the property is_draft,
        # which only works correctly once `_is_draft` is set.
        self._is_draft: bool = is_draft

        self.files: WrappedFiles = WrappedFiles(self)
        self._access_links: AccessLinks = AccessLinks(self)

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

    @property
    def is_published(self):
        """
        Return whether the current object represents an already published record.

        Files can only be modified for unpublished records.
        """
        return self._record.is_published

    def _expect_published(self):
        if self.is_draft or not self.is_published:
            raise TypeError("Operation supported only for published records!")

    @property
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
        # compare relevant contents
        same_access = drft.access == self._record.access
        same_metadata = drft.metadata == self._record.metadata
        same_files = drft.files._files == self.files._files  # compare unwrapped
        return same_access and same_metadata and same_files
        # TODO: track https://github.com/inveniosoftware/invenio-app-rdm/issues/1233

    @property
    def access_links(self):
        """Return interface for managing access links for this record."""
        self._expect_published()

        return self._access_links

    def edit(self):
        """
        Create or switch to an existing draft based on the current record version.

        This draft can be used to update the metadata of the published record version.
        For this, change metadata accordingly and call `save()` and `publish()`.

        This object will stay a draft until `publish()` is called.
        To get back from the draft to the original record, without publishing,
        just request it again from the repository.
        """
        self._expect_published()

        self._record = self._client.draft.from_record(self._record.id)
        # https://github.com/inveniosoftware/invenio-app-rdm/issues/1223 workaround
        # just pull the draft from the other endpoint
        # self._record = self._client.draft.get(self._record.id)
        self._is_draft = True

    def new_version(self):
        """
        Create or switch to an existing draft for a new version of the current record.

        This works like `edit()`, with the difference that in a new version
        it is possible to change the files as well, not only metadata.
        """
        self._expect_published()

        self._record = self._client.draft.new_version(self._record.id)
        self._is_draft = True  # must be set before loading files for correct behavior
        self.files = WrappedFiles(self)  # update files information

    def save(self):
        """
        Save changes to draft record.

        This commits the changes to this draft object to the Invenio RDM instance.

        Notice that if the draft belongs to a published record version,
        this will only affect the draft (i.e. the version accessed via `edit()`).
        The changes will only be visible to others after calling `publish()`.
        """
        self._expect_draft()

        self._record = self._client.draft.update(self._record)

    def _check_files_exist_if_enabled(self):
        if self.files.enabled and len(self.files) == 0:
            raise ValueError("Files are enabled, but none are attached!")

    def publish(self):
        """
        Publish the draft as the actual record.

        Notice that:
        * a published record cannot be deleted
        * you can only change metadata of the record for that version (with `edit()`)
        * to also change files, you must create a new version (with `new_version()`)
        """
        self._expect_draft()
        self._check_files_exist_if_enabled()

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
    def __repr__(self):
        # little hack to show files properly
        f = self._record.files
        self._record.files = list(self.files.keys())  # type: ignore
        ret = repr(self._record)
        self._record.files = f
        return ret


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
        self._record: WrappedRecord = rec
        self._link: AccessLink = lnk

    @property
    def expires_at(self) -> Optional[datetime]:
        self._check_deleted()
        return self._link.expires_at

    @expires_at.setter
    def expires_at(self, value: Optional[datetime]):
        self._check_deleted()
        self._link.expires_at = value
        self._record._client.record.access_links.update(self._record.id, self._link)

    @property
    def permission(self) -> Optional[LinkPermission]:
        self._check_deleted()
        return self._link.permission

    @permission.setter
    def permission(self, value: Optional[LinkPermission]):
        self._check_deleted()
        self._link.permission = value
        self._record._client.record.access_links.update(self._record.id, self._link)

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
        self._record._client.record.access_links.delete(self._record.id, self._link.id)
        self._link = None  # type: ignore

    def _check_deleted(self):
        if self._link is None:
            raise ValueError("Invalid access link! Maybe you deleted it?")

    # magic methods must be proxied by hand
    def __str__(self):
        return str(self._link)


class AccessLinkQuery(Query):
    def __init__(self, rec: WrappedRecord):
        super().__init__()
        self._client: InvenioRDMClient = rec._client
        self._record: WrappedRecord = rec

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
        self._client: InvenioRDMClient = rec._client
        self._record: WrappedRecord = rec

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
    """Dict-like interface for interaction with files."""

    def __init__(self, record: WrappedRecord):
        self._record: WrappedRecord = record
        self._client: InvenioRDMClient = record._client

        # _files should contain the raw structure as returned by the API,
        # But this is only accessible if file support is enabled for the record.
        self._files: Files = record._record.files  # stub with just "enabled" state
        if record._record.files.enabled:
            self._files = self._get_fileinfos()

    def _get_fileinfos(self) -> Files:
        if self._record.is_draft:
            return self._client.draft.files(self._record.id)
        else:
            return self._client.record.files(self._record.id)

    @property
    def enabled(self) -> bool:
        return self._files.enabled

    @enabled.setter
    def enabled(self, value: bool):
        if self._files.entries is not None and len(self._files.entries) > 0:
            raise ValueError("This value can only be modified if there are no files!")

        # set files.enabled state on server without committing other record changes
        rec = self._client.draft.get(self._record.id)
        rec.files.enabled = value
        self._client.draft.update(rec)
        # if no exception happened, update the values locally
        self._record._record.files.enabled = value
        self._files.enabled = value
        if self._files.enabled and self._files.entries is None:
            self._files.entries = []

    def _check_mutable(self):
        if not self._record.is_draft or self._record.is_published:
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

        if self._record.is_draft:
            return self._client.draft.file_download(self._record.id, filename)
        else:
            return self._client.record.file_download(self._record.id, filename)

    def delete(self, filename: str):
        """Delete file from record draft."""
        self._check_mutable()
        self._check_filename(filename)

        self._record._client.draft.file_delete(self._record.id, filename)
        # if no exception happened, it worked ->
        # remove the entry locally (thereby avoid reloading data)
        assert self._files.entries is not None
        self._files.entries = [fm for fm in self._files.entries if fm.key != filename]

    def import_old(self):
        """Import files from the previous version."""
        self._check_mutable()
        self._check_enabled()
        if self._record.versions.index < 2:
            raise ValueError("Cannot import files, this is the first record version!")
        if self._files.entries is not None and len(self._files.entries) > 0:
            raise ValueError("Can only import if no new files were uploaded yet!")

        self._files = self._client.draft.files_import(self._record.id)

    def upload(self, filename: str, data: BinaryIO):
        """
        Upload a file.

        Takes a binary stream as input, you have to `open` your file yourself with `"rb"`.
        """
        self._check_mutable()
        self._check_enabled()
        self._check_filename(filename, False)

        self._client.draft.file_upload_start(self._record.id, filename)
        self._client.draft.file_upload_content(self._record.id, filename, data)
        self._client.draft.file_upload_complete(self._record.id, filename)
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
