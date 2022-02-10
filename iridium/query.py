"""
Access proxies for various entities.

These can be used to get lazy-loaded list-like sequences of query results
and also to access specific entities via their id using dict-like access.
"""

from .generic import AccessProxy, Query
from .inveniordm.api import InvenioRDMClient
from .inveniordm.models import Results, VocType
from .record import WrappedRecord


class VocabularyQuery(Query):
    DEF_BATCH_SIZE = 500

    def __init__(self, cl: InvenioRDMClient, voc_type: VocType, **kwargs):
        super().__init__(**kwargs)
        self._client = cl
        self._voc_type = voc_type

    def _query_items(self, **kwargs) -> Results:
        return self._client.query.vocabulary(self._voc_type, **kwargs)


class RecordQuery(Query):
    DEF_BATCH_SIZE = 10

    def __init__(self, cl: InvenioRDMClient, user_only: bool, **kwargs):
        super().__init__(**kwargs)
        self._client = cl
        self._user_only = user_only

    def _query_items(self, **kwargs) -> Results:
        ret = self._client.query.records(self._user_only, **kwargs)
        ret.hits.hits = list(
            map(lambda x: WrappedRecord(self._client, x, False), ret.hits.hits)
        )
        return ret


class DraftQuery(Query):
    DEF_BATCH_SIZE = 10

    def __init__(self, cl: InvenioRDMClient, **kwargs):
        super().__init__(**kwargs)
        self._client = cl

    def _query_items(self, **kwargs) -> Results:
        # a draft query is just a record query for unpublished records by the user
        if "q" not in kwargs:
            kwargs["q"] = ""
        kwargs["q"] += " is_published:false"

        ret = self._client.query.records(user=True, **kwargs)
        ret.hits.hits = list(
            map(lambda x: WrappedRecord(self._client, x, True), ret.hits.hits)
        )
        return ret


class Vocabulary(AccessProxy):
    """Access to vocabularies with list- and dict-like interface."""

    def __init__(self, client, voc_type: VocType):
        super().__init__(client)
        self._voc_type = voc_type

    def _get_query(self, **kwargs) -> Query:
        return VocabularyQuery(self._client, self._voc_type, **kwargs)

    def _get_entity(self, term_id: str):
        return self._client.query.term(self._voc_type, term_id)


class Records(AccessProxy):
    """Access to records with list- and dict-like interface."""

    def _get_query(self, **kwargs) -> Query:
        # Filter out "user" argument (to query only user records)
        # and separate from possible normal query arguments
        user: bool = False
        if "user" in kwargs:
            if not isinstance(kwargs["user"], bool):
                raise ValueError("'user' must be a bool!")
            user = kwargs["user"]
            del kwargs["user"]

        return RecordQuery(self._client, user, **kwargs)

    def _get_entity(self, record_id: str):
        return WrappedRecord(self._client, self._client.record.get(record_id), False)


class Drafts(AccessProxy):
    """
    Access to record drafts with list- and dict-like interface.

    Notice that this will only list:
    * new record drafts, and
    * new record version drafts.

    It will **not** find drafts of editing existing record versions by the user,
    as these drafts cannot be efficiently queried for (yet) due to the way
    the search indices in Invenio RDM are set up.
    (There exists `has_draft:true`, but this does not allow to filter for owned records).
    """

    def _get_query(self, **kwargs) -> Query:
        return DraftQuery(self._client, **kwargs)

    def _get_entity(self, draft_id: str):
        return WrappedRecord(self._client, self._client.draft.get(draft_id), True)

    # this fits here nicely
    def create(self):
        """Create an empty record draft."""
        return WrappedRecord(self._client, self._client.draft.create(), True)
