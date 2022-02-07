"""Generic useful classes for the API."""

import math
from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx

from .inveniordm.api import InvenioRDMClient
from .inveniordm.models import Results


class PaginatedList(Sequence):
    """
    List-like class abstracting away automatic loading of successive batches of results.

    Here, batches are 0-indexed and contain `self._BATCH_SIZE` elements per batch
    (specified during initialization of the instance).
    Can only be used for read-only access. Already retrieved pages are cached.

    Usage (for developers): Subclass and implement `_get_batch`.
    """

    DEF_BATCH_SIZE: int = 1000

    def __init__(self, batch_size: Optional[int] = None):
        """Initialize with a batch fetcher and possibly custom batch size."""
        self._BATCH_SIZE = batch_size or self.DEF_BATCH_SIZE
        self._total: Optional[int] = None
        self._results: Dict[int, Any] = {}

    @abstractmethod
    def _get_batch(self, bidx: int) -> Tuple[List[Any], int]:
        """
        Given batch number, return the batch and total number of available results.

        Must respect self._BATCH_SIZE for the pagination.
        Assumed to be idempotent, with second argument a constant.

        You probably want to use some low-level query API method for the implementation.
        """

    def _get_batch_and_cache(self, bidx: int):
        """Load the specified batch, cache results, set total length if unset."""
        res, num = self._get_batch(bidx)
        if self._total is None:
            self._total = num
        self._results[bidx] = res
        return res

    def __len__(self) -> int:
        """
        Get the number of results.

        This will load at most one batch (if none was loaded yet).
        """
        if not self._total:
            self._get_batch_and_cache(0)
        assert isinstance(self._total, int)
        return self._total

    def _index_to_batch(self, idx: int):
        """Convert item index to respective batch index based on set batch size."""
        return (math.floor(idx / self._BATCH_SIZE), idx % self._BATCH_SIZE)

    def __getitem__(self, idx):
        """
        Get an item by index.

        This will load at most one batch (if it is not cached yet).
        """
        if not isinstance(idx, int):
            raise TypeError("Index must be an int!")

        bidx, boff = self._index_to_batch(idx)
        if bidx < 0:
            raise IndexError(f"Index {idx} is out of range [0-{self._total-1}]!")

        # load batch if needed (unknown size or uncached index)
        if self._total is None or bidx not in self._results:
            self._get_batch_and_cache(bidx)

        assert self._total is not None
        if not (0 <= idx < self._total):  # really out of bounds
            raise IndexError(f"Index {idx} is out of range [0-{self._total-1}]!")

        return self._results[bidx][boff]

    class PaginatedListIterator(Iterator):
        def __init__(self, parent):
            self.idx = 0
            self.parent = parent

        def __iter__(self):
            return self

        def __next__(self):
            try:
                ret = self.parent[self.idx]
                self.idx += 1
                return ret
            except IndexError:
                raise StopIteration

    def __iter__(self):
        """Return an iterator that handles batch loading behind the scenes."""
        return PaginatedList.PaginatedListIterator(self)

    def __contains__(self, obj):
        """
        Check if a value is in the list.

        The default implementation is O(n), as it might load the full list.
        """
        return obj in iter(self)


class Query(PaginatedList):
    """
    Class for convenient access to query results (that are assumed to have an id).

    Allowed keyword arguments: normal query args, but without 'page'.

    Access through numeric index corresponds to entries in search result order.
    `__contains__` supports lookup by id string, but __getitem__ does not,
    because this would be extremely inefficient (for this, use `dict()`).

    Usage (for developers): Subclass and implement `_query_items`.
    """

    def __init__(self, **kwargs):
        pgsz = None
        if "size" in kwargs:
            pgsz = kwargs["size"]
            del kwargs["size"]
        if "page" in kwargs:
            raise ValueError("Forbidden keyword argument 'page'!")

        super().__init__(pgsz)
        self._query_args = kwargs

    def __contains__(self, obj):
        """
        Check whether a term exists in the query results.

        If given a string, will look for an entity with provided id.
        Otherwise, will compare the whole entity.
        """
        if isinstance(obj, str):
            return obj in iter(x.id for x in iter(self))
        else:
            super().__contains__(obj)

    @abstractmethod
    def _query_items(self, **kwargs) -> Results:
        """
        Override this with a function taking `QueryArgs` and returning `Results`.

        The `QueryArgs` are passed as individual keyword arguments.
        The `Results` must contain parsed entities in `hits.hits`.
        The entities must have a hashable `id` field.
        """

    def _get_batch(self, bidx):
        ret = self._query_items(
            page=bidx + 1, size=self._BATCH_SIZE, **self._query_args
        )
        return (ret.hits.hits, ret.hits.total)

    # convenience functions for dict-like access and interop:

    def dict(self):
        """Convert to a real `dict` (this downloads all query results!)."""
        return {r.id: r for r in self}

    def items(self) -> Iterable[Tuple[str, Any]]:
        """Return (id, result) key-value pais in query result order."""
        return map(lambda x: (x.id, x), iter(self))

    def keys(self) -> Iterable[str]:
        """Return ids of entities in query result order."""
        return map(lambda x: x.id, iter(self))

    def values(self) -> Iterable[Any]:
        """Return entities in query result order."""
        return iter(self)


class AccessProxy(ABC):
    """Access to individual entities as well as queries with applied filters."""

    def __init__(self, client: InvenioRDMClient):
        self._client = client

    def __call__(self, *args, **kwargs):
        return self._get_query(*args, **kwargs)

    @abstractmethod
    def _get_query(self, *args, **kwargs) -> Query:
        """
        Return a query configured to return certain results.

        Without arguments shall return all possible results.
        Otherwise should pass query arguments.
        """

    @abstractmethod
    def _get_entity(self, entity_id: str) -> Any:
        """
        Return an entity given its id.

        Override this with a low-level API function raising HTTPStatusError on failure.
        """

    def __getattr__(self, name: str):
        # mostly for dict(), keys(), values() and items()
        return self().__getattribute__(name)

    def __len__(self) -> int:
        """Return total number of accessible entities."""
        return len(self())

    def __iter__(self) -> Iterator:
        """Iterate through all accessible entities."""
        return iter(self())

    def __getitem__(self, key: str) -> Any:
        """Get an entity by id."""
        try:
            return self._get_entity(key)
        except httpx.HTTPStatusError as e:
            raise KeyError(e.response)

    def __contains__(self, obj: str) -> bool:
        """Check whether an entity exists."""
        try:
            self.__getitem__(obj)
            return True
        except KeyError:
            return False
