"""High-level API for Invenio RDM."""

from typing import Dict, Optional

from .inveniordm import InvenioRDMClient
from .inveniordm.models import VocType
from .query import Drafts, Records, Vocabulary


class Repository:
    """Class representing an InvenioRDM repository."""

    __slots__ = ["_client", "records", "drafts", "vocabulary"]

    def __init__(self, *args, **kwargs):
        """
        Create an instance of the high-level Invenio RDM API.

        Do not use directly. Use `connect` or `from_env` to get an instance.
        """
        if "client" in kwargs:
            self._client = kwargs["client"]
        else:
            self._client = InvenioRDMClient(*args, **kwargs)

        self.records: Records = Records(self._client)
        """Access interface for published records."""

        self.drafts: Drafts = Drafts(self._client)
        """Access interface for drafts."""

        self.vocabulary: Dict[str, Vocabulary] = {
            vt: Vocabulary(self._client, vt) for vt in VocType
        }
        """Access interface for vocabularies."""

    @classmethod
    def from_env(cls, **httpx_kwargs):
        """
        Get client instance based on configuration given in environment.

        The expected environment variables are `INVENIORDM_URL` and `INVENIORDM_TOKEN`.
        """
        return cls(client=InvenioRDMClient.from_env(**httpx_kwargs))

    @classmethod
    def connect(cls, url: str, token: Optional[str], **httpx_kwargs):
        """Get client instance based on provided credentials."""
        return cls(url, token, **httpx_kwargs)

    def connected(self) -> bool:
        """Check whether the configured Invenio RDM instance is accessible."""
        return self._client.connected()
