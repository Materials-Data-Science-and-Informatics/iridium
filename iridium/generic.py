"""Generic useful classes for the API."""

import math
from abc import abstractmethod
from collections.abc import Iterator, Sequence
from typing import Any, Dict, List, Optional, Tuple


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

        This will load at most one batch.
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

        If it is not in the batch cache, loads all batches up to it.
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
