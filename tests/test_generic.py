"""Test generic structures of the Iridium API."""
import math

import httpx
import pytest
from pydantic import BaseModel

from iridium.generic import AccessProxy, PaginatedList, Query
from iridium.inveniordm.models import ResultPage, Results


class LazyNumbers(PaginatedList):
    def __init__(self, pgsize: int, total: int):
        super().__init__(pgsize)
        self.tot = total

    def _get_batch(self, page: int):
        sz = self._BATCH_SIZE
        return (list(range(page * sz, min(self.tot, (page + 1) * sz))), self.tot)


class Dummy(BaseModel):
    key: str
    val: int

    def __init__(self, val):
        super().__init__(key=str(val), val=val)


class DummyQuery(Query):
    MAX = 10000

    def __init__(self, **kwargs):
        super().__init__("key", **kwargs)

    def _query_items(self, **kwargs):
        size = self._BATCH_SIZE
        page = 1
        end = self.MAX
        if "page" in kwargs:
            page = int(kwargs["page"])
        if "end" in kwargs:
            end = int(kwargs["end"])
        ret = list(range((page - 1) * size, min(end, self.MAX, page * size)))
        return Results(hits=ResultPage(total=end, hits=[Dummy(n) for n in ret]))


class DummyAccessProxy(AccessProxy):
    def __init__(self):
        # need no real client for these tests
        super().__init__(None)  # type: ignore

    def _get_query(self, **kwargs):
        return DummyQuery(**kwargs)

    def _get_entity(self, entity_id):
        if int(entity_id) >= DummyQuery.MAX:
            raise httpx.HTTPStatusError(
                request=None, response=None, message="number too large!"  # type: ignore
            )
        return Dummy(int(entity_id))


def test_lazy_results():
    # lazy list from 0-996 (987 entries, odd number on purpose to test non-full page)

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


def test_number_query():
    # should not accept page parameter (is managed internally)
    with pytest.raises(ValueError):
        DummyQuery(page=23)

    # access one element and check that only one page is loaded
    q = DummyQuery(size=250)
    assert q[123] == Dummy(123)
    assert q["123"] == Dummy(123)
    assert q._BATCH_SIZE == 250
    assert len(q) == DummyQuery.MAX
    assert len(q._results) == 1

    # check added dict-like behaviours
    assert "12345" not in q
    assert "321" in q
    assert Dummy(123) in q
    assert Dummy(12345) not in q
    assert list(q.values())[123] == Dummy(123)
    assert list(q.keys())[456] == "456"
    assert list(q.items())[789] == ("789", Dummy(789))
    assert q.dict() == {str(n): Dummy(n) for n in range(DummyQuery.MAX)}
    assert repr(q).find("['0', '1', '2'") == 0


def test_number_access_proxy():
    ap = DummyAccessProxy()
    with pytest.raises(TypeError):
        ap("non-kwarg")

    # test some pass-through operations
    assert len(ap) == DummyQuery.MAX
    assert len(ap(end=10)) == 10

    assert repr(ap).find("['0', '1', '2'") >= 0
    assert repr(ap(end=10)).find("['0', '1', '2'") >= 0

    # test __getattr__ and __iter__
    assert list(ap.keys()) == [str(n) for n in range(DummyQuery.MAX)]
    assert list(ap) == [Dummy(n) for n in range(DummyQuery.MAX)]

    # test __contains__
    assert "11" in ap
    assert "10" not in ap(end=10)
    assert "12345" not in ap  # via direct lookup
    assert "12345" not in ap()  # via query traversal
    with pytest.raises(TypeError):
        3.12 not in ap  # works only for int or string

    # test __getitem__
    assert ap[11] == Dummy(11)
    assert ap()[11] == Dummy(11)
    with pytest.raises(TypeError):
        ap[1.23]
    with pytest.raises(IndexError):
        ap(end=10)[11]
    with pytest.raises(KeyError):
        ap(end=10)["11"]
