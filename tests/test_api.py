"""Test high-level Iridium API."""

import pytest

from iridium.inveniordm.models import VocType, voc_class


@pytest.fixture(autouse=True)
def skip_if_no_invenio(irdm):
    """Automatically skip a test when Invenio RDM is not available."""
    if not irdm.connected():
        pytest.skip("no connection to Invenio RDM!")


def test_vocab(irdm):
    # all vocabularies should be able to return some first term
    # i.e. the endpoints all work and return the correct type of response
    for vt in VocType:
        assert isinstance(irdm.vocabulary[vt][0], voc_class(vt))

    # sanity-check default things
    assert len(irdm.vocabulary[VocType.resource_types]) == 33
    assert len(irdm.vocabulary[VocType.licenses](tags="software")) == 173
    assert len(irdm.vocabulary[VocType.languages](tags="extinct")) == 619
