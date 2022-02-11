"""Fixtures and general utilities for pytest test suite."""
import secrets
from datetime import datetime
from pathlib import Path
from typing import Optional

import pytest

from iridium.inveniordm.api import BibMetadata, InvenioRDMClient

DUMMYFILE_NAMELEN = 8
DUMMYFILE_SIZE = 1024


class UtilFuncs:
    """Helpers used in tests."""

    @staticmethod
    def random_hex(length: int) -> str:
        """Return hex string of given length."""
        return secrets.token_hex(int(length / 2))

    @staticmethod
    def default_bib_metadata():
        """Minimal sufficient metadata for a record yielding no errors."""
        return BibMetadata.parse_obj(
            {
                "title": "Untitled Dataset",
                "creators": [
                    {
                        "person_or_org": {
                            "type": "personal",
                            "given_name": "Unknown",
                            "family_name": "Author",
                        }
                    }
                ],
                "publication_date": datetime.strftime(datetime.now(), "%Y-%m-%d"),
                "resource_type": {"id": "other"},
            }
        )


@pytest.fixture(scope="session")
def testutils():
    """Fixture giving access to helper functions anywhere in test suite."""
    return UtilFuncs


@pytest.fixture(scope="session")
def dummy_file(testutils, tmp_path_factory):
    """Create dummy files and clean them up in the end."""
    dummy_base: Path = tmp_path_factory.mktemp("dummy_files")
    files = []

    def _dummy_file(name: Optional[str] = None, content: Optional[str] = None) -> Path:
        if name in files:
            raise RuntimeError(f"Dummy file {name} already exists!")

        filename = name if name else testutils.random_hex(DUMMYFILE_NAMELEN)
        while filename in files:
            filename = testutils.random_hex(DUMMYFILE_NAMELEN)
        filepath = dummy_base / filename

        content = content if content else testutils.random_hex(DUMMYFILE_SIZE)

        with open(filepath, "w") as file:
            assert content is not None
            file.write(content)
            file.flush()
        return filepath

    yield _dummy_file

    for file in files:
        if file.is_file():
            file.unlink()


@pytest.fixture(scope="session")
def rdm():
    """Return an API instance configured from environment variables."""
    cl = InvenioRDMClient.from_env(verify=False)

    # clean up all drafts from possible previous unclean runs
    if cl.connected():
        drafts = cl.query.records(user=True, q="is_published:false")
        for d in drafts.hits.hits:
            cl.draft.delete(d.id)

    return cl


@pytest.fixture(scope="session")
def get_test_record(rdm, testutils):
    """
    If no testing record exists yet, create fresh and return id.

    If testing record exists, return id of (draft of) latest version.
    If tsuf is passed, will append the string to the description for logging.
    If publish is passed, the draft is published, so it returns just a record id.

    This is used to work on the same record chain while testing the API, avoiding
    spamming the Instance with a lot of testing records per run of the test suite.
    """
    rec_id = None

    def _get_test_record(tsuf: Optional[str] = "", publish=False):
        nonlocal rec_id
        if rec_id is None:
            drft = rdm.draft.create(metadata=testutils.default_bib_metadata())
            drft.files.enabled = False
            drft.metadata.title = f"Test {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            drft.metadata.description = ""
            if tsuf:
                drft.metadata.description += f"{tsuf}<br>\n"

            rdm.draft.update(drft)
            if publish:
                rdm.draft.publish(drft.id)
            rec_id = drft.id
            return rec_id
        else:
            drft = rdm.draft.from_record(rdm.record.latest_version(rec_id).id)
            if tsuf:
                drft.metadata.description += f"{tsuf}<br>\n"

            drft = rdm.draft.update(drft)
            if publish:
                rdm.draft.publish(drft.id)
            return drft.id

    yield _get_test_record
