"""Test high-level Iridium API."""

import time
from datetime import datetime

import httpx
import pytest

from iridium.inveniordm.models import LinkPermission, VocType, voc_class
from iridium.record import WrappedRecord
from iridium.util import hashsum


@pytest.fixture(autouse=True)
def skip_if_no_invenio(irdm):
    """Automatically skip a test when Invenio RDM is not available."""
    if not irdm.connected():
        pytest.skip("no connection to Invenio RDM!")


def test_vocab_query(irdm):
    # all vocabularies should be able to return some first term
    # i.e. the endpoints all work and return the correct type of response
    for vt in VocType:
        assert isinstance(irdm.vocabulary[vt][0], voc_class(vt))

    # sanity-check default things
    assert len(irdm.vocabulary[VocType.resource_types]) == 33
    assert len(irdm.vocabulary[VocType.licenses](tags="software")) == 173
    assert len(irdm.vocabulary[VocType.languages](tags="extinct")) == 619


def test_readonly_fields_draft(irdm):
    draft = irdm.drafts.create()
    assert isinstance(draft, WrappedRecord)

    # should not be able to add new things
    with pytest.raises(ValueError):
        draft.something = "value"

    # should not be able to modify certain public things...
    # ...from wrapped record
    with pytest.raises(ValueError):
        draft.id = "foo"
    with pytest.raises(ValueError):
        draft.pids = "foo"
    # ...and also from wrapper itself
    with pytest.raises(ValueError):
        draft.is_draft = "foo"  # type: ignore
    with pytest.raises(ValueError):
        draft.access_links = "foo"  # type: ignore
    with pytest.raises(ValueError):
        draft.files = "foo"  # type: ignore
    with pytest.raises(ValueError):
        draft.versions = "foo"  # type: ignore

    # try invalid methods
    with pytest.raises(TypeError):
        draft.edit()
    with pytest.raises(TypeError):
        draft.access_links
    with pytest.raises(TypeError):
        draft.versions

    # check that valid things are listed (examples)
    assert "id" in dir(draft)
    assert "parent" in dir(draft)

    # delete and check that it worked
    did = draft.id
    draft.delete()
    assert not draft.is_draft
    with pytest.raises(AttributeError):
        draft.metadata.title
    assert did not in irdm.drafts()


def test_create_record(irdm, testutils, dummy_file):

    # edit/new version fails for invalid
    with pytest.raises(httpx.HTTPStatusError):
        irdm.drafts.create("INVALID_ID", True)
    with pytest.raises(httpx.HTTPStatusError):
        irdm.drafts.create("INVALID_ID", False)

    time.sleep(1)
    assert len(irdm.drafts) == 0

    # create new draft
    draft = irdm.drafts.create()
    assert draft.id not in irdm.records

    # check it was created successfully
    time.sleep(1)
    assert irdm.drafts[0].id == draft.id

    # check defaults
    assert draft.is_draft
    assert not draft.is_published
    assert draft.files.enabled

    with pytest.raises(ValueError):
        draft.files.import_old()  # should not work (1st version)

    # try publishing -> should fail with exception
    with pytest.raises(ValueError):
        draft.publish()

    draft.metadata = testutils.default_bib_metadata()
    assert not draft.is_saved()
    errs = draft.save()
    assert draft.is_saved()
    assert len(errs) == 1  # should still complain about missing files

    # publishing -> should still fail
    with pytest.raises(ValueError):
        draft.publish()

    draft.files.enabled = False
    assert draft.is_saved()  # should affect and sync state immediately
    draft.publish()  # now it should work
    assert draft.is_saved()  # just published obviously should still be saved

    time.sleep(1)
    assert len(irdm.drafts) == 0  # not a draft anymore
    assert not draft.is_draft  # locally also switched status
    assert len(draft.versions) == 1

    # these should not work anymore (not a draft now)
    with pytest.raises(TypeError):
        draft.save()
    with pytest.raises(TypeError):
        draft.publish()
    with pytest.raises(TypeError):
        draft.delete()

    # now let's edit the title

    draft.edit()
    assert draft.is_draft
    assert draft.is_published  # because we edit existing now

    # should not be able to change that while editing old version
    with pytest.raises(ValueError):
        draft.files.enabled = True

    draft.metadata.title += " (updated)"
    assert not draft.is_saved()
    assert draft.save() is None
    assert draft.is_saved()

    draft.publish()
    assert irdm.records[draft.id].metadata.title == draft.metadata.title
    assert draft.versions.latest().id == draft.id
    assert draft.is_saved  # non-draft is of course also saved

    with pytest.raises(ValueError):  # try invalid query to versions
        draft.versions(invalid="argument")

    # and now lets do a new version:
    ver2 = draft.versions.create()
    assert ver2.metadata.publication_date is None
    assert ver2.is_draft
    assert not ver2.is_published

    # lets do some file stuff

    ver2.metadata.title += " (w/files)"
    ver2.metadata.publication_date = "2022"
    assert list(ver2.files.keys()) == []

    # uploading should fail while files are disabled
    testfile = dummy_file("test.txt", "hello world")
    with pytest.raises(ValueError):
        ver2.files.upload(testfile)

    # enable uploads, add file, check, get it back, remove it again
    ver2.files.enabled = True
    ver2.files.upload(testfile)
    assert list(ver2.files.keys()) == ["test.txt"]
    with pytest.raises(ValueError):  # uploading to same name should fail
        ver2.files.upload(testfile)
    assert ver2.files["test.txt"].checksum[4:] == hashsum(
        testutils.text2data("hello world"), "md5"
    )
    assert ver2.files.download("test.txt").read() == b"hello world"
    ver2.files.delete("test.txt")
    with pytest.raises(ValueError):  # deleting non-existing should also fail
        ver2.files.delete("test.txt")
    assert list(ver2.files.keys()) == []

    # upload from a stream into some filename
    ver2.files.upload("test.md", testutils.text2data("Hello, InvenioRDM!"))

    with pytest.raises(ValueError):  # switching files off now should fail
        ver2.files.enabled = False

    # publish version and check its now the latest
    ver2.publish()
    assert ver2.version == 2
    assert ver2.is_latest
    time.sleep(1)
    assert not irdm.records[draft.id].is_latest
    assert draft.versions[draft.id].id == draft.id
    assert draft.versions.latest().id == ver2.id

    # check we can download the file from the published version
    assert ver2.files.download("test.md").read() == b"Hello, InvenioRDM!"

    # test remaining dict- and related funcs
    fk = list(ver2.files.keys())[0]
    fv = list(ver2.files.values())[0]
    assert ver2.files[fk] == fv
    assert list(ver2.files.items())[0] == (fk, fv)
    assert next(iter(ver2.files)) == fk
    assert len(ver2.files) == 1

    # create another version and play around with files

    ver3 = ver2.versions.create()
    ver3.metadata.publication_date = "2022"  # need to add this

    # the file enabled status should not change between versions
    assert ver3.files.enabled
    # assume the backend always gives us the same "new version", however we ask for it
    assert draft.versions.create().id == ver3.id
    # assume that the new version has the files not included by default
    assert list(ver3.files.keys()) == []

    ver3.files.import_old()
    assert list(ver3.files.keys()) == ["test.md"]

    with pytest.raises(ValueError):
        ver3.files.import_old()  # should not work (only allowed when nothing's there)

    # we can remove the imported file again...
    ver3.files.delete("test.md")
    assert list(ver3.files.keys()) == []
    # ... and add it back another time
    ver3.files.import_old()
    assert list(ver3.files.keys()) == ["test.md"]
    # and check its correct
    assert ver3.files.download("test.md").read() == b"Hello, InvenioRDM!"

    # now add another file
    ver3.files.upload("other.txt", testutils.text2data("Hello, again!"))
    assert set(ver3.files.keys()) == set(["test.md", "other.txt"])

    ver3.publish()

    assert len(ver3.access_links) == 0
    lnk = ver3.access_links.create()
    assert len(ver3.access_links) == 1
    assert ver3.access_links[0].id == lnk.id

    # try setting and reading
    dt = datetime.now()
    lnk.expires_at = dt
    assert lnk.expires_at == dt
    perm = LinkPermission.EDIT
    lnk.permission = perm
    assert lnk.permission == perm

    # check read-only fields
    with pytest.raises(AttributeError):
        lnk.id = "somethingelse"
    with pytest.raises(AttributeError):
        lnk.token = "somethingelse"
    with pytest.raises(AttributeError):
        lnk.created_at = dt

    # check the query works and we can get the link back
    assert ver3.access_links[lnk.id].id == lnk.id
    # check the query rejects invalid kwargs
    with pytest.raises(ValueError):
        assert ver3.access_links(bla="invalid")

    lnk.delete()
    assert len(ver3.access_links) == 0  # link should be gone

    # now nothing should work for the object
    with pytest.raises(ValueError):
        lnk.id
    with pytest.raises(ValueError):
        lnk.token
    with pytest.raises(ValueError):
        lnk.created_at

    with pytest.raises(ValueError):
        lnk.expires_at
    with pytest.raises(ValueError):
        lnk.permission
