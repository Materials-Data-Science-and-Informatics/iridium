"""Modified base model with enhanced pretty-printing."""

import json
from typing import cast

from pydantic import BaseModel

from ...pprint import pp


class JSONModel(BaseModel):
    """
    Subclass adding additional features to pydantic BaseModel for API responses.

    Models deriving from this variant:
    * automatically are pretty-printed as JSON (for user convenience)
    * can have read-only attributes declared that prevent direct setting
    * can be toggled to return original, raw JSON dict (for debugging)

    Only use this for parsing JSON responses from API requests!
    Otherwise these enhancements might lead to unintended consequences.
    """

    @property
    def _read_only(self):
        return []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __setattr__(self, key, value):
        if key in self._read_only:
            raise AttributeError(f"'{key}' is a read-only attribute!")
        super().__setattr__(key, value)

    _raw_json: bool = False

    @classmethod
    def raw_json(cls, val: bool):
        cls._raw_json = val

    def __repr__(self) -> str:
        """
        Pretty-printed appropriate representation of JSON-based objects.

        In normal circumstances, this should be __str__ instead, because __repr__
        is supposed to REPRoduce the object, i.e. be a Python expression yielding the
        object.

        But in our case the distinction between "user" and "developer" is not that
        clear-cut and as users will use this in a Python interpreter context,
        making this __repr__ seems to be the lesser evil for enhanced usability.
        """
        return pp(json.loads(self.json(exclude_none=True)))

    @classmethod
    def parse_obj(cls, val, *args, **kwargs):
        """
        If _raw_json is set, return back the raw JSON dict instead of parsed object.

        NOTE: This is a DEBUGGING HACK and should only be used as such!
        """
        if cls._raw_json:
            return cast(cls, val)
        else:
            return cast(cls, super().parse_obj(val, *args, **kwargs))
