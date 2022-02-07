"""Higher-level API for Invenio RDM."""

from typing import Any, Dict

from .generic import AccessProxy, Query
from .inveniordm import models as m
from .inveniordm.api import InvenioRDMClient


class RecordQuery(Query):
    def __init__(self, cl: InvenioRDMClient, user_only: bool, **kwargs):
        super().__init__(**kwargs)
        self._client = cl
        self._user_only = user_only

    def _query_items(self, **kwargs):
        return self._client.query.records(self._user_only, **kwargs)


class VocabularyQuery(Query):
    def __init__(self, cl: InvenioRDMClient, voc_type: m.VocType, **kwargs):
        super().__init__(**kwargs)
        self._client = cl
        self._voc_type = voc_type

    def _query_items(self, **kwargs):
        return self._client.query.vocabulary(self._voc_type, **kwargs)


class Records(AccessProxy):
    """Access to records with list- and dict-like interface."""

    def _get_query(self, user: bool = False, *args, **kwargs) -> Query:
        """Query for a subset of records (returns a sequence)."""
        return RecordQuery(self._client, user, **kwargs)

    def _get_entity(self, record_id: str):
        return self._client.record.get(record_id)


class Vocabulary(AccessProxy):
    """Access to vocabularies with list- and dict-like interface."""

    def __init__(self, client, voc_type: m.VocType):
        super().__init__(client)
        self._voc_type = voc_type

    def _get_query(self, **kwargs):
        """Query for a subset of terms (returns a sequence)."""
        return VocabularyQuery(self._client, self._voc_type, **kwargs)

    def _get_entity(self, term_id: str):
        return self._client.query.term(self._voc_type, term_id)


class Repository:
    """Class representing an InvenioRDM repository."""

    def __init__(self, *args, **kwargs):
        if "client" in kwargs:
            self._client = kwargs["client"]
        else:
            self._client = InvenioRDMClient(*args)

        self.records = Records(self._client)
        self.vocabulary = {vt: Vocabulary(self._client, vt) for vt in m.VocType}

    @staticmethod
    def from_env(httpx_kwargs: Dict[str, Any] = {}):
        return Repository(client=InvenioRDMClient.from_env(httpx_kwargs))

    def connected(self) -> bool:
        return self._client.connected()
