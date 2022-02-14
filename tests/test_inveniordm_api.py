"""Tests for Invenio RDM backend API."""

import time
from datetime import date

import httpx
import pytest

from iridium.inveniordm.models import LinkPermission, VocType
from iridium.util import hashsum

# NOTE: The tests assume that there is a default instance with default demo data
# each test run will create one new record with multiple versions!


@pytest.fixture(autouse=True)
def skip_if_no_invenio(rdm):
    """Automatically skip a test when Invenio RDM is not available."""
    if not rdm.connected():
        pytest.skip("no connection to Invenio RDM!")


def test_vocabularies(rdm):
    """Test queries to vocabularies."""
    with pytest.raises(httpx.HTTPStatusError):
        rdm.query.vocabulary("invalid_voc")

    res = rdm.query.vocabulary(VocType.resource_types)
    assert res.hits.total == 33

    lcs = rdm.query.vocabulary(VocType.licenses)
    assert lcs.hits.total == 418

    sjs = rdm.query.vocabulary(VocType.subjects)
    assert sjs.hits.total == 48

    lgs = rdm.query.vocabulary(VocType.languages)
    assert lgs.hits.total == 7847

    assert rdm.query.vocabulary(VocType.languages, tags="extinct").hits.total == 619

    lg = rdm.query.vocabulary(VocType.licenses, suggest="gli")
    assert lg.hits.total == 1
    assert lg.hits.hits[0].id == "glide"

    with pytest.raises(httpx.HTTPStatusError):
        rdm.query.term("license", "invalid_license")

    gl = rdm.query.term(VocType.licenses, "glide")
    assert gl.id == "glide"


def test_record_queries(rdm):
    """Test queries to records."""
    # check that there are no old pending drafts around
    drafts = rdm.query.records(user=True, q="is_published:false")
    assert drafts.hits.total == 0

    # try using elastic search query syntax to find some default record
    assert rdm.query.records().hits.total > 0


def test_new_draft(rdm, dummy_file, get_test_record, testutils):
    """Test creating, editing and finally destroying a draft."""
    # create fresh record draft
    drft = rdm.draft.create(metadata=testutils.default_bib_metadata())

    # try removing title and publish (should fail, as title is mandatory)
    drft.metadata.title = ""
    d2 = rdm.draft.update(drft)
    assert len(d2.errors) > 0
    d3 = rdm.draft.get(drft.id)
    assert d3.errors is None
    with pytest.raises(httpx.HTTPStatusError):
        rdm.draft.publish(drft.id)

    # re-add a title
    drft.metadata.title = "Test title"
    d4 = rdm.draft.update(drft)
    d4 = rdm.draft.get(drft.id)
    assert d4.metadata.title == drft.metadata.title

    # test file management

    # default `get` does not contain metadata about individual files
    assert d4.files.entries is None
    # but the extra `files` endpoint provides that information
    assert rdm.draft.files(drft.id).entries == []

    somefile = dummy_file("test.txt")

    # file is not there yet
    with pytest.raises(httpx.HTTPStatusError):
        rdm.draft.file_metadata(drft.id, somefile.name)

    fs = rdm.draft.file_upload_start(drft.id, somefile.name)
    assert fs.entries is not None
    assert len(fs.entries) == 1
    assert fs.entries[0].status == "pending"

    fs2 = rdm.draft.file_upload_content(drft.id, somefile.name, open(somefile, "rb"))
    assert fs.entries[0] == fs2

    # check that upload is completed successfully and checksum is correct
    fs3 = rdm.draft.file_upload_complete(drft.id, somefile.name)
    assert fs3.status == "completed"
    assert fs3.checksum is not None
    alg, hsum = fs3.checksum.split(":")
    hsum_verify = hashsum(open(somefile, "rb"), alg)
    assert hsum == hsum_verify

    # check that metadata of file is now as expected:
    # except of metadata field and updated date they should agree
    fs4 = rdm.draft.file_metadata(drft.id, somefile.name)
    assert fs3.updated <= fs4.updated
    assert fs3.metadata is None
    fs3.metadata = fs4.metadata
    fs3.updated = fs4.updated
    assert fs3 == fs4

    # check that we can download the file back:
    with open(somefile, "rb") as f:
        fileorig = f.read()
    fileback = rdm.draft.file_download(drft.id, somefile.name).read()
    assert fileback == fileorig

    # now remove the file again
    rdm.draft.file_delete(drft.id, somefile.name)

    # file is not there anymore
    with pytest.raises(httpx.HTTPStatusError):
        rdm.draft.file_metadata(drft.id, somefile.name)
    assert rdm.draft.files(drft.id).entries == []

    # remove the record draft and check it is really gone
    rdm.draft.delete(d2.id)
    with pytest.raises(httpx.HTTPStatusError):
        rdm.draft.get(drft.id)


def test_draft_from_record(rdm, get_test_record):
    """Test that published record metadata can be edited."""
    urec = rdm.record.get(get_test_record("edit_meta", publish=True))

    drft = rdm.draft.from_record(urec.id)
    drft.metadata.description += "Updated after publish"
    rdm.draft.update(drft)
    rdm.draft.publish(urec.id)

    drft = rdm.draft.from_record(urec.id)
    drft.metadata.description += ", twice.<br>"
    rdm.draft.update(drft)
    rdm.draft.publish(urec.id)

    # veryify the twice updated and published metadata
    urec2 = rdm.record.get(urec.id)
    assert urec2.metadata.description == drft.metadata.description

    # try to add a file to same version -> should fail
    drft = rdm.draft.from_record(urec.id)
    with pytest.raises(httpx.HTTPStatusError) as exc:
        rdm.draft.file_upload_start(drft.id, "some_file.txt")
    assert exc.value.response.status_code == 403


def test_version_from_record(rdm, get_test_record, dummy_file):
    """Test creating new versions with same and different files."""
    # 1st version: metadata only
    drft = rdm.record.get(get_test_record("new_versions", publish=True))

    file1 = dummy_file("test1.txt")
    file2 = dummy_file("test2.txt")
    file3 = dummy_file("test3.txt")
    hsum2 = hashsum(open(file2, "rb"), "md5")
    hsum3 = hashsum(open(file3, "rb"), "md5")

    # 2nd version: enable files, add test1.txt
    drft = rdm.draft.new_version(drft.id)
    drft.files.enabled = True
    drft.metadata.publication_date = date.today()  # is empty for some reason
    rdm.draft.update(drft)
    rdm.draft.file_upload(drft.id, file1)
    rdm.draft.publish(drft.id)
    rec = rdm.record.get(drft.id)

    # check that the upload into the record succeeded
    rfiles = rdm.record.files(rec.id)
    assert rfiles.enabled
    rfmeta = rdm.record.file_metadata(rec.id, file1.name)
    assert rfmeta.key == file1.name

    # 3rd version: del test1.txt, add test2.txt as test1.txt add test3.txt
    drft = rdm.draft.new_version(drft.id)
    drft.metadata.publication_date = date.today()  # is empty for some reason
    rdm.draft.update(drft)

    rdm.draft.files_import(drft.id)
    rdm.draft.file_delete(drft.id, file1.name)
    rdm.draft.file_upload_start(drft.id, file1.name)
    rdm.draft.file_upload_content(drft.id, file1.name, open(file2, "rb"))
    rdm.draft.file_upload_complete(drft.id, file1.name)
    rdm.draft.file_upload(drft.id, file3)
    rdm.draft.publish(drft.id)

    # verify that the operations succeeded and we have now the expected files
    rec = rdm.record.get(drft.id)
    rfiles = rdm.record.files(rec.id)
    print(rfiles)
    hsums = {fm.key: fm.checksum.split(":")[1] for fm in rfiles.entries}
    assert hsums == {"test1.txt": hsum2, "test3.txt": hsum3}
    with open(file3, "rb") as f:
        assert f.read() == rdm.record.file_download(rec.id, "test3.txt").read()

    time.sleep(1)  # apparently needs time for version to be indexed in elastic
    assert rdm.record.versions(rec.id).hits.total == 3
    assert rdm.record.latest_version(rec.id) == rec


def test_access_links(rdm, get_test_record):
    """Test creating, updating and removing access links to a record."""
    rec = rdm.record.get(get_test_record("access_links", publish=True))

    assert rdm.record.access_links.list(rec.id).hits.total == 0

    lnk = rdm.record.access_links.create(rec.id)
    assert rdm.record.access_links.get(rec.id, lnk.id) == lnk
    assert rdm.record.access_links.list(rec.id).hits.total == 1

    lnk.permission = LinkPermission.EDIT
    rdm.record.access_links.update(rec.id, lnk)
    assert rdm.record.access_links.get(rec.id, lnk.id).permission == LinkPermission.EDIT

    rdm.record.access_links.delete(rec.id, lnk.id)
    assert rdm.record.access_links.list(rec.id).hits.total == 0
