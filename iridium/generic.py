"""
Generic useful classes for the high-level API.

`AccessProxy` serves as the wrapper class to accessing various entities
that are returned by InvenioRDM from its ElasticSearch index.

This includes: records, drafts, versions, access links, vocabularies and more.
"""

import math
from abc import ABC, abstractmethod
from typing import (
    Dict,
    Generic,
    Iterable,
    Iterator,
    List,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
)

import httpx

from .inveniordm import InvenioRDMClient
from .inveniordm.models import Results

T = TypeVar("T")
S = TypeVar("S")


class PaginatedList(Sequence[T]):
    """
    List-like class abstracting away automatic loading of successive batches of results.

    Here, batches are 0-indexed and contain `self._BATCH_SIZE` elements per batch
    (specified during initialization of the instance).

    Can only be used for read-only access. Already retrieved pages are cached.
    """

    DEF_BATCH_SIZE: int = 1000
    """Default batch size for instances. Up to ~2000 works fine."""

    def __init__(self, batch_size: Optional[int] = None):
        """
        Initialize with a batch fetcher and possibly custom batch size.

        A small batch size is useful to get a first preview without loading everything,
        while a larger batch size is more efficient for traversing all results.
        """
        self._BATCH_SIZE: int = batch_size or self.DEF_BATCH_SIZE
        self._total: Optional[int] = None
        self._results: Dict[int, List[T]] = {}

    @abstractmethod
    def _get_batch(self, bidx: int) -> Tuple[List[T], int]:
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
            raise IndexError(f"Index {idx} is out of range!")

        # load batch if needed (unknown size or uncached index)
        if self._total is None or bidx not in self._results:
            self._get_batch_and_cache(bidx)

        assert self._total is not None
        if not (0 <= idx < self._total):  # really out of bounds
            raise IndexError(f"Index {idx} is out of range!")

        return self._results[bidx][boff]

    class PaginatedListIterator(Iterator[S]):
        def __init__(self, parent):
            self.idx = 0
            self.parent = parent

        def __iter__(self):
            return self

        def __next__(self) -> S:
            try:
                ret = self.parent[self.idx]
                self.idx += 1
                return ret
            except IndexError:
                raise StopIteration

    def __iter__(self) -> Iterator[T]:
        """Return an iterator that handles batch loading behind the scenes."""
        return PaginatedList.PaginatedListIterator(self)

    def __contains__(self, obj) -> bool:
        """
        Check if a value is in the list.

        The default implementation is O(n), as it might load the full list.
        """
        return obj in iter(self)


# TODO: probably this should be refactored into paginated and unpaginated queries
# and build using composition instead of inheritance
# (i.e. support batched vs unbatched result providers)


class Query(PaginatedList[T]):
    """
    Class for convenient access to query results.

    Results are by default assumed to have a string `id` attribute for dict-like access.

    Allowed keyword arguments: normal `QueryArgs`, but without `page`.

    Access through numeric index corresponds to entries in search result order.

    Access through string id is possible, but inefficient (may traverse all results).
    """

    def __init__(self, dict_key: str = "id", **kwargs):
        pgsz = None
        if "size" in kwargs:
            pgsz = kwargs["size"]
            del kwargs["size"]
        if "page" in kwargs:
            raise ValueError("Forbidden keyword argument 'page'!")

        super().__init__(pgsz)
        self._dict_key = dict_key
        self._query_args = kwargs

    @abstractmethod
    def _query_items(self, **kwargs) -> Results[T]:
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
        return {r.__dict__[self._dict_key]: r for r in iter(self)}

    # these behave like a dict, but are lazy (not pulling everything, unless forced),
    # could be useful to list "the first few results":

    def items(self) -> Iterable[Tuple[str, T]]:
        """Return (id, result) key-value pais in query result order."""
        return ((x.__dict__[self._dict_key], x) for x in iter(self))

    def keys(self) -> Iterable[str]:
        """Return ids of entities in query result order."""
        return (x.__dict__[self._dict_key] for x in iter(self))

    def values(self) -> Iterable[T]:
        """Return entities in query result order."""
        return iter(self)

    # as a generic preview we can just list the ids (more would be verbose):
    def __repr__(self) -> str:
        """Print ids of all accessible entities (this will load all of them)."""
        return repr(list(self.keys()))

    # Provided for consistency with AccessProxy.__contains__
    # (even though its inefficient for a query):

    def __contains__(self, obj):
        """
        Check whether an entity exists in the query results.

        If given a string, will look for an entity with provided id.
        Otherwise, will compare the whole entity. O(n)
        """
        if isinstance(obj, str):
            return obj in self.keys()
        else:
            return super().__contains__(obj)

    def __getitem__(self, key):  # -> T
        """
        Get an entity.

        If passed a string, will look up by id (inefficiently, O(n)).
        If passed an int, will perform filterless query and take n-th result.
        """
        if isinstance(key, str):
            try:
                return next((k, v) for k, v in self.items() if k == key)[1]
            except StopIteration:
                raise KeyError
        else:
            return super().__getitem__(key)


class AccessProxy(ABC, Generic[T]):
    """
    Access to individual entities as well as queries with applied filters.

    Filtering, i.e. queries, are performed by calling an instance with query parameters.

    Without query parameters the object behaves like an unfiltered query.

    Direct access to entities is performed by accessing them by their id like a dict.

    So given an instance `foos`:
    * you can access a specific entry via `foos[FOO_ID]`
    * you can check whether `FOO_ID in foos`
    * you can filter using `foos(q="search terms")`
    * `foos` and `foos(...)` can be treated like a list of results.
    """

    def __init__(self, client: InvenioRDMClient):
        # only initialized here for convenience of _get_query and _get_entity
        self._client = client

    def __call__(self, *args, **kwargs):
        if len(args) > 0:  # to give more helpful error message than the default
            raise TypeError("Only keyword parameters may be passed to the query!")
        return self._get_query(**kwargs)

    @abstractmethod
    def _get_query(self, **kwargs) -> Query[T]:
        """
        Return a query configured to return certain results.

        Without arguments shall return all possible results without filtering.
        Otherwise should pass on query arguments and provide filtered results.
        """

    @abstractmethod
    def _get_entity(self, entity_id: str) -> T:
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

    def __iter__(self) -> Iterator[T]:
        """Iterate through all accessible entities."""
        return iter(self())

    def __repr__(self) -> str:
        """Print ids of all accessible entities."""
        return repr(self())

    def __getitem__(self, key):  # -> T
        """
        Get an entity.

        If passed a string, will look up by id.
        If passed an int, will perform filterless query and take n-th result.
        """
        if isinstance(key, str):
            try:
                return self._get_entity(key)
            except httpx.HTTPStatusError as e:
                raise KeyError(e.response)
        elif isinstance(key, int):
            return self()[key]
        else:
            raise TypeError("Passed key must be either string id or an int!")

    def __contains__(self, obj: str) -> bool:
        """Check whether an entity with given id exists."""
        try:
            self.__getitem__(obj)
            return True
        except KeyError:
            return False
