"""Higher-level API for Invenio RDM."""

from .inveniordm.api import InvenioRDMClient
from .inveniordm.models import VocType
from .query import Drafts, Records, Vocabulary


class Repository:
    """Class representing an InvenioRDM repository."""

    __slots__ = ["_client", "records", "drafts", "vocabulary"]

    def __init__(self, *args, **kwargs):
        if "client" in kwargs:
            self._client = kwargs["client"]
        else:
            self._client = InvenioRDMClient(*args)

        self.records = Records(self._client)
        self.drafts = Drafts(self._client)
        self.vocabulary = {vt: Vocabulary(self._client, vt) for vt in VocType}

    @staticmethod
    def from_env(**httpx_kwargs):
        return Repository(client=InvenioRDMClient.from_env(**httpx_kwargs))

    def connected(self) -> bool:
        return self._client.connected()
