"""Helper functions to allow using JSON and YAML interchangably and taking care of $refs."""

import hashlib
import io
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Set, Union
from urllib.parse import urlparse
from urllib.request import urlopen

from jsonschema import Draft7Validator, RefResolver
from jsonschema.exceptions import ValidationError
from pydantic import BaseModel
from ruamel.yaml import YAML

yaml = YAML(typ="safe")

JSON_v = Union[None, bool, int, float, str]
"""JSON primitive values."""

UnsafeJSON = Union[JSON_v, List[JSON_v], Mapping[str, Any]]
"""Superficial JSON type (not recursive!) to have at least some annotations."""


# TODO: based on referenced_schemas, create function
# to assemble self-contained schema and resolving everything


def loads_json(dat: str) -> UnsafeJSON:
    """Load YAML/JSON from a string."""
    res = None
    try:
        res = json.loads(dat)
    except json.JSONDecodeError:
        res = yaml.load(io.StringIO(dat))
    return res


def save_json(obj: BaseModel, filepath: Path):
    """Store a pydantic model serialized to JSON into a file."""
    with open(filepath, "w") as file:
        file.write(obj.json())
        file.flush()


def load_json(
    filename: Union[Path, str], basepath: Union[Path, str] = ""
) -> UnsafeJSON:
    """Load JSON from a file or URL. On failure, terminate program (fatal error)."""
    filename = str(filename) if isinstance(filename, Path) else filename
    basepath = str(basepath) if isinstance(basepath, Path) else basepath

    parsed = urlparse(filename)
    if parsed.scheme == "":
        filename = str(Path(basepath) / filename)
    elif parsed.scheme == "local":
        filename = filename.replace("local://", basepath + "/")
    elif parsed.scheme == "file":
        filename = filename.replace("file://", "")

    dat = None
    if parsed.scheme in ["", "local", "file"]:  # looks like a file
        dat = open(filename, "r").read()
    elif parsed.scheme.find("http") == 0:  # looks like a HTTP(S) URL
        dat = urlopen(str(filename)).read().decode("utf-8")

    if dat is not None:
        return loads_json(dat)
    return None


def validate_json(
    instance: UnsafeJSON,
    schema: UnsafeJSON,
    refSchemas: Optional[Dict[str, UnsafeJSON]] = None,
) -> Optional[ValidationError]:
    """Validate JSON against JSON Schema, on success return None, otherwise the error."""
    if refSchemas is None:
        refSchemas = {}
    try:
        resolver = RefResolver.from_schema(schema, store=refSchemas)
        validator = Draft7Validator(schema, resolver=resolver)
        validator.validate(instance)
        return None
    except ValidationError as e:
        return e


def referenced_schemas(schema: UnsafeJSON) -> Set[str]:
    """Return set of referenced external schemas within given schema."""
    if isinstance(schema, list):
        ret = {ref for s in schema for ref in referenced_schemas(s)}
        return ret
    elif isinstance(schema, dict):
        ret = {ref for v in schema.values() for ref in referenced_schemas(v)}
        if "$ref" in schema and isinstance(schema["$ref"], str):
            path = schema["$ref"].split("#")[0]  # without the fragment
            if len(path) > 0:  # not a local ref like #/...
                ret.add(path)
        return ret
    else:  # primitive type -> no ref
        return set()


def get_env(varname, defval=None):
    """Get environment variable. If no default value is missing, raise a runtime error."""
    env = os.environ.get(varname, defval)
    if not env:
        raise RuntimeError(f"{varname} is not set in shell environment or .env file!")
    return env


_hash_alg = {
    "md5": hashlib.md5,
    "sha1": hashlib.sha1,
    "sha256": hashlib.sha256,
    "sha512": hashlib.sha512,
}


def hashsum(file: Path, alg: str):
    """Compute hashsum for a file using selected algorithm."""
    try:
        h = _hash_alg[alg]()
    except KeyError:
        raise ValueError(f"Unsupported hashsum: {alg}")

    with open(file, "rb") as f:
        while True:
            chunk = f.read(h.block_size)
            if not chunk:
                break
            h.update(chunk)

    return h.hexdigest()
