"""Hash helper required by the unchanged reviewed numerical identity module."""
import hashlib
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
