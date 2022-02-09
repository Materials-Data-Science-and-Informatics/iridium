"""Utilities for pretty printing."""

import pprint
import sys
from typing import Any, Dict

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


class NoPrint:
    """Wrap any class to avoid printing it."""

    def __init__(self, obj):
        self.obj = obj

    def __repr__(self) -> str:
        return f"{type(self.obj).__name__}(...)"
