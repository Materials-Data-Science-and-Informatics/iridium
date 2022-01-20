"""Modified base model with enhanced pretty-printing."""

import json
import pprint
import sys
from typing import Any, Dict, cast

from pydantic import BaseModel


class JSONModel(BaseModel):
    """
    Subclass adding additional features to pydantic BaseModel for API responses.

    Models deriving from this variant:
    * automatically are pretty-printed as JSON (for user convenience)
    * can be toggled to return original, raw JSON dict (for debugging)

    Only use this for parsing JSON responses from API requests!
    Otherwise these enhancements might lead to unintended consequences.
    """

    _pprint_args: Dict[str, Any] = {
        "indent": 2,
        "depth": 4,
    }
    # TODO pydantic json args (exclude none etc)

    _raw_json: bool = False

    @classmethod
    def raw_json(cls, val: bool):
        cls._raw_json = val

    @classmethod
    def pprint_set(cls, **kwargs):
        """
        Set or remove arguments for the pretty-printer.

        This will immediately modify the pretty-printing of all subclasses.
        """
        for k, v in kwargs.items():
            if v is not None:
                cls._pprint_args[k] = v
            elif k in cls._pprint_args:
                del cls._pprint_args[k]

    def __str__(self) -> str:
        """Override for a configurable pretty-printed representation of objects."""
        return pprint.pformat(
            json.loads(self.json(exclude_none=True)),
            **JSONModel._pprint_args,
        )

    @classmethod
    def parse_obj(cls, val, *args, **kwargs):
        """
        If _raw_json is set, return back the raw JSON dict instead of parsed object.

        Note that this is a debugging hack and should only be used as such!
        """
        if cls._raw_json:
            return cast(cls, val)
        else:
            return cast(cls, super().parse_obj(val, *args, **kwargs))


if sys.version_info >= (3, 8):
    JSONModel.pprint_set(sort_dicts=False)
