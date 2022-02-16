"""
Low-level InvenioRDM REST API wrapper.

The classes in this module just neatly organize the endpoints to be
conveniently accessed through an `InvenioRDMClient` instance.

The methods return plain [pydantic](https://pydantic-docs.helpmanual.io/)
models that serve as somewhat validated Python representation of
the corresponding request and response JSON objects.

The 1-to-1 mapping between REST API endpoints and methods and the plain nature of
the request/response objects are useful due to the ease of debugging,
because there is no complex mutable state and no "magic" involved.
Working with this API is essentially like using `curl`.

**You probably should not use this API directly**,
unless the high-level API does not suit your needs for some reason.
If you do want to use it, you are basically on your own - consult the official
[InvenioRDM documentation](https://inveniordm.docs.cern.ch/reference/rest_api_index/)
and then find the corresponding methods in this module.
"""

from __future__ import annotations

import json
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, BinaryIO, Dict, Optional

import httpx
from dotenv import load_dotenv

from ..util import get_env, hashsum
from .models import (
    AccessControl,
    AccessLink,
    AccessPolicy,
    BibMetadata,
    FileMetadata,
    Files,
    LinkPermission,
    PIDs,
    Record,
    RecQueryArgs,
    Results,
    VocQueryArgs,
    VocType,
    voc_class,
    voc_special,
)

# TODO: if big file downloads make problems with memory, check out client.stream()

_debug = False
"""If set to true, will print HTTP returned exceptions."""


def _raise_on_error_status(r):
    """Raise an exception on 4XX and 5XX status codes + print the response body, if any."""
    try:
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        if _debug:
            print(
                f"Error response {e.response.status_code} while requesting {e.request.url!r}:"
            )
            try:
                print(json.dumps(e.response.json(), indent=2))
            except json.JSONDecodeError:
                print(e.response.text)  # Annoying if it is a huge HTML page
        raise e


class InvenioRDMClient:
    """Class for access to the InvenioRDM API."""

    def _endpoint(self, path: str) -> str:
        """Return complete URL based on configured base URL and relative API path."""
        return f"{self.irdm_url}/api{path}"

    def __init__(self, irdm_url: str, irdm_token: Optional[str] = None, **httpx_kwargs):
        """
        Create an instance of the InvenioRDM API.

        The instance is configured for the provided credentials and arguments.
        """
        headers: Dict[str, str] = {}
        if httpx_kwargs and "headers" in httpx_kwargs:
            headers = httpx_kwargs["headers"]
            del httpx_kwargs["headers"]
        if irdm_token:
            headers["Authorization"] = f"Bearer {irdm_token}"
        self.client = httpx.Client(headers=headers, **httpx_kwargs)

        self.irdm_url = irdm_url.rstrip("/")
        self.query = QueryAPI(self)
        self.record = RecordAPI(self)
        self.draft = DraftAPI(self)

    def __del__(self):
        """Destructor for API object (to silence weird exception on close)."""
        try:
            self.client.close()
        except AttributeError:
            pass

    def connected(self) -> bool:
        """Check that InvenioRDM is accessible."""
        try:
            r = self.client.get(self._endpoint("/records?size=1"))
            _raise_on_error_status(r)
            return True
        except:  # noqa: E722
            return False

    @staticmethod
    def from_env(**httpx_kwargs):
        """
        Get client instance based on configuration given in environment.

        The expected environment variables are `INVENIORDM_URL` and `INVENIORDM_TOKEN`.
        """
        load_dotenv()  # get environment variables from possible .env file
        url = get_env("INVENIORDM_URL").rstrip("/")
        token = get_env("INVENIORDM_TOKEN")
        return InvenioRDMClient(url, token, **httpx_kwargs)


class SubAPI:
    """InvenioRDM sub-API class."""

    def __init__(self, client: InvenioRDMClient):
        """Initialize sub-API with the main API (to access shared information)."""
        self._p = client


class QueryAPI(SubAPI):
    """Query sub-API for vocabularies and records."""

    def vocabulary(self, voc_type: VocType, **kwargs) -> Results:
        """
        Get the specified vocabulary term names.

        https://inveniordm.docs.cern.ch/reference/rest_api_vocabularies/
        """
        pref = "/vocabularies" if not voc_special(voc_type) else ""
        pcls = voc_class(voc_type)

        qargs = VocQueryArgs.parse_obj(kwargs)
        url = self._p._endpoint(f"{pref}/{voc_type}")
        url += f"?{qargs}"
        r = self._p.client.get(url)
        _raise_on_error_status(r)

        res = Results.parse_obj(r.json())
        if isinstance(res, Results):  # if not using JSONModel.raw_json "hack"
            res.parse_hits(pcls)
        return res

    def term(self, voc_type: VocType, term_id: str) -> Any:
        """
        Get the specified vocabulary term definition.

        https://inveniordm.docs.cern.ch/reference/rest_api_vocabularies/#get-a-vocabulary-record
        """
        pref = "/vocabularies" if not voc_special(voc_type) else ""
        pcls = voc_class(voc_type)

        r = self._p.client.get(self._p._endpoint(f"{pref}/{voc_type}/{term_id}"))
        _raise_on_error_status(r)

        return pcls.parse_obj(r.json())

    def records(self, user: Optional[bool] = False, **kwargs) -> Results:
        """
        Query records using ElasticSearch.

        If user=True, will only query within records of the user.

        https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#search-records
        https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#user-records
        """
        qargs = RecQueryArgs.parse_obj(kwargs)
        usr = "/user" if user else ""

        url = self._p._endpoint(f"{usr}/records{'?' if qargs else ''}{qargs}")
        r = self._p.client.get(url)
        _raise_on_error_status(r)

        res = Results.parse_obj(r.json())
        if isinstance(res, Results):  # if not using JSONModel.raw_json "hack"
            res.parse_hits(Record)
        return res


class AccessLinkAPI(SubAPI):
    """Access link sub-API."""

    def list(self, record_id: str) -> Results:
        """
        Link access links for record.

        https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#list-access-links
        """
        r = self._p.client.get(self._p._endpoint(f"/records/{record_id}/access/links"))
        _raise_on_error_status(r)

        res = Results.parse_obj(r.json())
        if isinstance(res, Results):  # if not using JSONModel.raw_json "hack"
            res.parse_hits(AccessLink)
        return res

    def get(self, record_id: str, link_id: str) -> AccessLink:
        """
        Get information about access link for record.

        https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#get-an-access-link
        """
        url = self._p._endpoint(f"/records/{record_id}/access/links/{link_id}")
        r = self._p.client.get(url)
        _raise_on_error_status(r)
        return AccessLink.parse_obj(r.json())

    def delete(self, record_id: str, link_id: str):
        """
        Get information about access link for record.

        https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#get-an-access-link
        """
        url = self._p._endpoint(f"/records/{record_id}/access/links/{link_id}")
        r = self._p.client.delete(url)
        _raise_on_error_status(r)

    def create(
        self,
        record_id: str,
        expires_at: Optional[datetime] = None,
        permission: Optional[LinkPermission] = None,
        link_id: Optional[str] = None,
    ) -> AccessLink:
        """
        Create an access link for a record (or update, if link_id is provided).

        https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#create-an-access-link
        """
        create = link_id is None
        if create and not permission:
            permission = LinkPermission.VIEW
        assert permission is not None

        req = {}
        if create or permission:
            req["permission"] = permission.value
        if expires_at:
            req["expires_at"] = expires_at.isoformat()

        url = f"/records/{record_id}/access/links" + ("" if create else f"/{link_id}")
        if create:
            r = self._p.client.post(self._p._endpoint(url), json=req)
        else:  # update
            r = self._p.client.patch(self._p._endpoint(url), json=req)
        _raise_on_error_status(r)
        return AccessLink.parse_obj(r.json())

    def update(self, record_id: str, aclnk: AccessLink) -> AccessLink:
        """
        Update an access link for a record (from a modified access link object).

        https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#update-an-access-link
        """
        return self.create(record_id, aclnk.expires_at, aclnk.permission, aclnk.id)


class RecordAPI(SubAPI):
    """Record sub-API."""

    def __init__(self, client: InvenioRDMClient):  # noqa: D107
        super().__init__(client)
        self.access_links = AccessLinkAPI(client)

    def get(self, record_id: str) -> Record:
        """
        Get a published record (does not contain information about files).

        https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#get-a-record
        """
        r = self._p.client.get(self._p._endpoint(f"/records/{record_id}"))
        _raise_on_error_status(r)
        return Record.parse_obj(r.json())

    def files(self, record_id: str) -> Files:
        """
        List files attached to a record.

        Notice that this contains more information than is included in `RecordAPI.get`.

        https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#list-a-drafts-files
        """
        r = self._p.client.get(self._p._endpoint(f"/records/{record_id}/files"))
        _raise_on_error_status(r)
        return Files.parse_obj(r.json())

    def file_metadata(self, record_id: str, filename: str) -> FileMetadata:
        """
        Get metadata of a record file.

        https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#get-a-record-files-metadata
        """
        url = self._p._endpoint(f"/records/{record_id}/files/{filename}")
        r = self._p.client.get(url)
        _raise_on_error_status(r)
        return FileMetadata.parse_obj(r.json())

    def file_download(self, record_id: str, filename: str) -> BytesIO:
        """
        Download file from a record.

        https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#download-a-record-file
        """
        url = self._p._endpoint(f"/records/{record_id}/files/{filename}/content")
        r = self._p.client.get(url)
        _raise_on_error_status(r)
        return BytesIO(r.content)

    def versions(self, record_id: str) -> Results:
        """
        Get all versions of a record.

        Basically searches for all entries with same parent.id and sorts by version.

        https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#get-all-versions
        """
        # url = self._p._endpoint(f"/records/{record_id}/versions")
        # buggy; see https://github.com/inveniosoftware/invenio-app-rdm/issues/1167
        url = self._p._endpoint(f"/records/{record_id}/versions?allversions=true")
        r = self._p.client.get(url)
        _raise_on_error_status(r)

        res = Results.parse_obj(r.json())
        if isinstance(res, Results):  # if not using JSONModel.raw_json "hack"
            res.parse_hits(Record)
        return res

    def latest_version(self, record_id: str) -> Record:
        """
        Get latest version of a record.

        https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#get-latest-version
        """
        url = self._p._endpoint(f"/records/{record_id}/versions/latest")
        r = self._p.client.get(url, follow_redirects=True)
        _raise_on_error_status(r)
        return Record.parse_obj(r.json())


class DraftAPI(SubAPI):
    """Draft sub-API."""

    def get(self, draft_id: str) -> Record:
        """
        Get metadata of a record draft (does not contain information about files).

        https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#get-a-draft-record
        """
        r = self._p.client.get(self._p._endpoint(f"/records/{draft_id}/draft"))
        _raise_on_error_status(r)
        return Record.parse_obj(r.json())

    def delete(self, draft_id: str):
        """
        Delete a record draft.

        https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#get-a-draft-record
        """
        r = self._p.client.delete(self._p._endpoint(f"/records/{draft_id}/draft"))
        _raise_on_error_status(r)

    def publish(self, draft_id: str) -> Record:
        """
        Publish a record draft.

        https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#publish-a-draft-record
        """
        url = self._p._endpoint(f"/records/{draft_id}/draft/actions/publish")
        r = self._p.client.post(url)
        _raise_on_error_status(r)
        return Record.parse_obj(r.json())

    def from_record(self, record_id: str) -> Record:
        """
        Create a draft from a published record version (to update attached metadata).

        https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#edit-a-published-record-create-a-draft-record-from-a-published-record
        """
        r = self._p.client.post(self._p._endpoint(f"/records/{record_id}/draft"))
        _raise_on_error_status(r)
        return Record.parse_obj(r.json())

    def new_version(self, record_id: str) -> Record:
        """
        Create a draft from a published record as a new version (that gets a new id).

        The publication_date and version are removed, versions.index is incremented
        and a new id is provided for the new version.

        https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#create-a-new-version
        """
        r = self._p.client.post(self._p._endpoint(f"/records/{record_id}/versions"))
        _raise_on_error_status(r)
        return Record.parse_obj(r.json())

    def create(
        self,
        metadata: Optional[BibMetadata] = None,
        access: Optional[AccessControl] = None,
        files: Optional[Files] = None,
        draft_id: Optional[str] = None,
        pids: PIDs = None,
    ) -> Record:
        """
        Create a record draft (or update an existing draft, if draft_id provided).

        https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#create-a-draft-record
        """
        create = draft_id is None

        # add dummy values if none provided to create minimal accepted draft
        if create:
            # if not metadata:
            #     metadata = default_bib_metadata()
            if not access:
                access = AccessControl(
                    record=AccessPolicy.PUBLIC, files=AccessPolicy.PUBLIC
                )
            if not files:
                files = Files(enabled=True)

        req = {}
        if metadata is not None:
            req["metadata"] = json.loads(metadata.json(exclude_none=True))
        if access is not None:
            req["access"] = json.loads(access.json(exclude_none=True))
        if files is not None:
            req["files"] = json.loads(files.json(exclude_none=True))

        # This was undocumented, but is required - otherwise the record breaks on update
        if not create and pids is not None:
            req["pids"] = json.loads(pids.json(exclude_none=True))

        url = self._p._endpoint("/records" + ("" if create else f"/{draft_id}/draft"))
        if create:
            r = self._p.client.post(url, json=req)
        else:  # update
            r = self._p.client.put(url, json=req)
        _raise_on_error_status(r)

        return Record.parse_obj(r.json())

    def update(self, draft: Record) -> Record:
        """
        Update a record draft (from a modified draft object).

        https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#update-a-draft-record
        """
        return self.create(
            draft.metadata, draft.access, draft.files, draft.id, draft.pids
        )

    def files(self, draft_id: str) -> Files:
        """
        List files attached to a record draft.

        Notice that this contains more information than is included in `DraftAPI.get`.

        https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#list-a-drafts-files
        """
        r = self._p.client.get(self._p._endpoint(f"/records/{draft_id}/draft/files"))
        _raise_on_error_status(r)
        return Files.parse_obj(r.json())

    def file_metadata(self, draft_id: str, filename: str) -> FileMetadata:
        """
        Get metadata of a record draft file.

        https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#get-a-record-files-metadata
        """
        url = self._p._endpoint(f"/records/{draft_id}/draft/files/{filename}")
        r = self._p.client.get(url)
        _raise_on_error_status(r)
        return FileMetadata.parse_obj(r.json())

    def file_download(self, draft_id: str, filename: str) -> BytesIO:
        """
        Download file from a record draft.

        https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#download-a-record-file
        """
        url = self._p._endpoint(f"/records/{draft_id}/draft/files/{filename}/content")
        r = self._p.client.get(url)
        _raise_on_error_status(r)
        return BytesIO(r.content)

    def file_delete(self, draft_id: str, filename: str):
        """
        Delete a file from the record draft.

        https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#delete-a-draft-file
        """
        url = self._p._endpoint(f"/records/{draft_id}/draft/files/{filename}")
        r = self._p.client.delete(url)
        _raise_on_error_status(r)

    def file_upload_start(self, draft_id: str, filename: str) -> Files:
        """
        Register a new file upload for the record draft.

        https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#start-draft-file-uploads
        """
        url = self._p._endpoint(f"/records/{draft_id}/draft/files")
        r = self._p.client.post(url, json=[{"key": filename}])
        _raise_on_error_status(r)
        return Files.parse_obj(r.json())

    def file_upload_complete(self, draft_id: str, filename: str) -> FileMetadata:
        """
        Mark an upload as completed.

        https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#complete-a-draft-file-upload
        """
        url = self._p._endpoint(f"/records/{draft_id}/draft/files/{filename}/commit")
        r = self._p.client.post(url)
        _raise_on_error_status(r)
        return FileMetadata.parse_obj(r.json())

    def file_upload_content(
        self, draft_id: str, filename: str, data: BinaryIO
    ) -> FileMetadata:
        """
        Upload file content to a registered filename.

        https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/#upload-a-draft-files-content
        """
        url = self._p._endpoint(f"/records/{draft_id}/draft/files/{filename}/content")
        hdr = {"content-type": "application/octet-stream"}
        r = self._p.client.put(url, content=data, headers=hdr)
        _raise_on_error_status(r)
        return FileMetadata.parse_obj(r.json())

    def files_import(self, draft_id: str) -> Files:
        """
        Import all files from previous version.

        (**NOTE:** undocumented in the official API docs)
        """
        url = self._p._endpoint(f"/records/{draft_id}/draft/actions/files-import")
        r = self._p.client.post(url)
        _raise_on_error_status(r)
        return Files.parse_obj(r.json())

    def file_upload(self, draft_id: str, file: Path) -> FileMetadata:
        """Upload a file for a record draft and verify checksum (convenience function)."""
        assert file.is_file()

        self.file_upload_start(draft_id, file.name)
        self.file_upload_content(draft_id, file.name, open(file, "rb"))

        fmeta = self.file_upload_complete(draft_id, file.name)
        assert fmeta.checksum is not None
        alg, hsum = fmeta.checksum.split(":")
        hsum_verify = hashsum(open(file, "rb"), alg)
        assert hsum == hsum_verify

        return fmeta
