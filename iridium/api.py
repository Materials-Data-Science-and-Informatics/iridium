"""Higher-level API for Invenio RDM."""

from typing import Any, Dict

import httpx

from .generic import PaginatedList
from .inveniordm import models as m
from .inveniordm.api import InvenioRDMClient


class Vocabulary(PaginatedList):
    """
    Class for convenient access to vocabularies with list- and dict-like interface.

    Access through numeric index corresponds to entries in search result order,
    Access through string identifier will look up the specified term.

    Allowed keyword arguments: `VocQueryArgs` without 'page'
    """

    def __init__(self, cl: InvenioRDMClient, voc_type: m.VocType, **kwargs):
        pgsz = None
        if "size" in kwargs:
            pgsz = kwargs["size"]
            del kwargs["size"]
        if "page" in kwargs:
            raise ValueError("Forbidden keyword argument 'page'!")

        super().__init__(pgsz)
        self._client = cl
        self._voc_type = voc_type
        self._query_args = kwargs

    def _get_batch(self, bidx):
        ret = self._client.query.vocabulary(
            self._voc_type, page=bidx + 1, size=self._BATCH_SIZE, **self._query_args
        )
        return (ret.hits.hits, ret.hits.total)

    def __getitem__(self, key):
        if isinstance(key, int):
            return super().__getitem__(key)
        if isinstance(key, str):
            try:
                return self._client.query.term(self._voc_type, key)
            except httpx.HTTPStatusError as e:
                raise KeyError(e.response)
        raise TypeError("Key must be an int or str!")

    def __contains__(self, obj):
        """
        Check whether a term exists in the vocabulary query results.

        If given a string, will perform O(1) lookup.
        Otherwise, will need O(n) to load all results.
        """
        if isinstance(obj, str):
            # if string, interpret as term id and look it up directly in DB
            try:
                self.__getitem__(obj)
                return True
            except KeyError:
                return False
        else:  # inefficient list traversal
            super().__contains__(obj)

    def dict(self):
        """Convert to a real `dict` (this downloads all query results!)."""
        return {r.id: r for r in self}


class Repository:
    """Class representing an InvenioRDM repository."""

    def __init__(self, *args, **kwargs):
        if "client" in kwargs:
            self._client = kwargs["client"]
        else:
            self._client = InvenioRDMClient(*args)

    @staticmethod
    def from_env(httpx_kwargs: Dict[str, Any] = {}):
        return Repository(client=InvenioRDMClient.from_env(httpx_kwargs))

    def connected(self) -> bool:
        return self._client.connected()

    def vocabulary(self, voc_type: m.VocType, **kwargs):
        return Vocabulary(self._client, voc_type, **kwargs)
