"""
Access proxies for various entities.

These can be used to get lazy-loaded list-like sequences of query results
and also to access specific entities via their id using dict-like access.

Notice that other query types are located in different places in order to
prevent circular dependencies. For example, access link or version queries
for published records are colocated with the `WrappedRecord` class that
is used to access these queries.
"""
from typing import Optional

from .generic import AccessProxy, Query
from .inveniordm import InvenioRDMClient
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
        ret.hits.hits = [WrappedRecord(self._client, x) for x in ret.hits.hits]
        return ret


class DraftQuery(Query):
    DEF_BATCH_SIZE = 10

    def __init__(self, cl: InvenioRDMClient, **kwargs):
        super().__init__(**kwargs)
        self._client = cl

    def _query_items(self, **kwargs) -> Results:
        if "user" in kwargs:  # must be true anyway, forbid overriding it
            raise ValueError("'user' is not allowed as a keyword argument here!")
        # a draft query is just a record query for unpublished records by the user
        if "q" not in kwargs:
            kwargs["q"] = ""
        kwargs["q"] += " is_published:false"

        ret = self._client.query.records(user=True, **kwargs)
        # HACK because is_draft is broken:
        for x in ret.hits.hits:
            x.is_draft = True
        # ----

        ret.hits.hits = [WrappedRecord(self._client, x) for x in ret.hits.hits]
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
        # the user flag determines whether general or user record API is used
        return RecordQuery(self._client, user, **kwargs)

    def _get_entity(self, record_id: str):
        return WrappedRecord(self._client, self._client.record.get(record_id))


class Drafts(AccessProxy):
    """
    Access to record drafts with list- and dict-like interface.

    Notice that this will only list:
    * new record drafts, and
    * new record version drafts.

    It will **not** find drafts of editing existing record versions by the user,
    as these drafts cannot be efficiently queried for (yet) due to the way
    the search indices in InvenioRDM are set up.
    (There exists `has_draft:true`, but this does not allow to filter for owned records).
    See: https://github.com/inveniosoftware/invenio-app-rdm/issues/714
    """

    def _get_query(self, **kwargs) -> Query:
        return DraftQuery(self._client, **kwargs)

    def _get_entity(self, draft_id: str):
        return WrappedRecord(self._client, self._client.draft.get(draft_id))

    # this fits here nicely as a general way to create new drafts
    def create(
        self, record_id: Optional[str] = None, new_version: bool = True
    ) -> WrappedRecord:
        """
        Create an empty draft, create new version or edit an existing record.

        If `record_id` is `None`, will create an empty draft.
        Otherwise will return a draft for an existing or new version
        (depending on whether `new_version` is set) for the passed `record_id`.
        """
        if record_id is None:
            rec = self._client.draft.create()
        else:
            # this is also accessible from the WrappedRecord,
            # but we can save one GET request doing it directly
            if new_version:
                rec = self._client.draft.new_version(record_id)
            else:
                rec = self._client.draft.from_record(record_id)

        return WrappedRecord(self._client, rec)
