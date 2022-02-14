"""Helper functions."""

import hashlib
import os
from typing import BinaryIO


def get_env(var_name, def_val=None):
    """
    Get environment variable.

    If no default value is given and value is missing, raises a runtime error.
    """
    env = os.environ.get(var_name, def_val)
    if not env:
        raise RuntimeError(f"{var_name} is not set in shell environment or .env file!")
    return env


_hash_alg = {
    "md5": hashlib.md5,
    "sha1": hashlib.sha1,
    "sha256": hashlib.sha256,
    "sha512": hashlib.sha512,
}


def hashsum(data: BinaryIO, alg: str):
    """Compute hashsum from given binary file stream using selected algorithm."""
    try:
        h = _hash_alg[alg]()
    except KeyError:
        raise ValueError(f"Unsupported hashsum: {alg}")

    while True:
        chunk = data.read(h.block_size)
        if not chunk:
            break
        h.update(chunk)

    return h.hexdigest()
