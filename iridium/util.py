"""Helper functions to allow using JSON and YAML interchangably and taking care of $refs."""

import hashlib
import os
from pathlib import Path


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
