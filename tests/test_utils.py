"""Test pprint and general utilities."""

from io import BytesIO

import pytest
from pydantic import BaseModel

from iridium.pprint import NoPrint, PrettyRepr, pprint_args
from iridium.util import get_env, hashsum


class InnermostDummy(BaseModel):
    waldo: bool


class InnerDummy(BaseModel):
    foo: int
    bar: str
    baz: InnermostDummy


class Dummy(BaseModel):
    qux: InnerDummy
    quy: InnerDummy
    quz: InnerDummy


def test_print_wrappers():
    inner = InnerDummy(foo=1337, bar="InvenioRDM", baz=InnermostDummy(waldo=True))
    obj = Dummy(baz=inner, qux=inner, quy=inner, quz=inner)

    assert repr(NoPrint(obj)) == "Dummy(...)"

    d = pprint_args["depth"]  # save default depth

    pprint_args["depth"] = 1
    expect = "{'qux': {...}, 'quy': {...}, 'quz': {...}}"
    assert repr(PrettyRepr(obj.dict())) == expect

    pprint_args["depth"] = 2
    expect = (
        "{ 'qux': {'bar': 'InvenioRDM', 'baz': {...}, 'foo': 1337},\n"
        "  'quy': {'bar': 'InvenioRDM', 'baz': {...}, 'foo': 1337},\n"
        "  'quz': {'bar': 'InvenioRDM', 'baz': {...}, 'foo': 1337}}"
    )
    assert repr(PrettyRepr(obj.dict())) == expect

    pprint_args["depth"] = d  # restore to default


def test_utils():
    with pytest.raises(KeyError) as e:
        get_env("INVALID_ENV_VAR")
    assert str(e).find("not set in shell")
    assert get_env("INVALID_ENV_VAR", 42) == 42

    data = BytesIO("InvenioRDM".encode("utf8"))
    assert hashsum(data, "md5") == "880bb95f87e3f62058528f6f50b6c374"
    with pytest.raises(ValueError):
        hashsum(data, "invalid")
