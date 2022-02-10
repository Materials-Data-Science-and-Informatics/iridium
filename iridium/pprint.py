"""Utilities for pretty printing."""

import pprint
import sys
from typing import Any, Dict

import wrapt

pprint_args: Dict[str, Any] = {
    "indent": 2,
    "depth": 4,
}
"""Globally used pprint settings."""

if sys.version_info >= (3, 8):
    pprint_args["sort_dicts"] = False


def pp(obj) -> str:
    """Pretty print object (using global pprint_args)."""
    return pprint.pformat(obj, **pprint_args)


class NoPrint(wrapt.ObjectProxy):
    """Wrap any class to avoid printing it."""

    def __repr__(self) -> str:
        return f"{type(self.__wrapped__).__name__}(...)"


class PrettyRepr(wrapt.ObjectProxy):
    """Wrap any class to apply pretty-printing to it."""

    def __repr__(self) -> str:
        return pp(self.__wrapped__)
