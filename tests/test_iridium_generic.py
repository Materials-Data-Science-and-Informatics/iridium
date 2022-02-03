"""Test generic structures of the Iridium API."""
import math

import pytest

from iridium.generic import PaginatedList


class LazyNumbers(PaginatedList):
    def __init__(self, pgsize: int, total: int):
        super().__init__(pgsize)
        self.tot = total

    def _get_batch(self, page: int):
        sz = self._BATCH_SIZE
        return (list(range(page * sz, min(self.tot, (page + 1) * sz))), self.tot)


def test_lazy_results():
    # lazy list from 0-996 (987 entries)

    LIMIT = 987
    nums = LazyNumbers(10, LIMIT)

    assert len(nums) == LIMIT
    assert nums[0] == 0
    assert nums[23] == 23
    assert nums[LIMIT - 1] == LIMIT - 1

    # check that only required batches are loaded until now
    assert len(nums._results[0]) == 10
    assert len(nums._results[98]) == 7
    assert set(nums._results.keys()) == {0, 2, 98}

    # check invalid lookups
    with pytest.raises(IndexError):
        nums[-1]
    with pytest.raises(IndexError):
        nums[LIMIT]
    with pytest.raises(TypeError):
        nums["invalid key"]  # type: ignore

    # check iterator behavior (should return all entries)
    ls = []
    for num in nums:
        ls.append(num)
    assert len(nums._results) == math.ceil(LIMIT / 10)
    assert ls == list(range(LIMIT))
    # check we actually get fresh iterator each time
    assert next(iter(nums)) == 0
    assert next(iter(nums)) == 0

    # check __contains__
    assert 0 in nums
    assert 123 in nums
    assert 986 in nums
    assert -1 not in nums
    assert 1234 not in nums
    assert "invalid" not in nums
