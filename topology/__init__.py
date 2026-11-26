"""Read an ordered network path and identify a particular traversal of a hop."""

import json
from pathlib import Path

from .catalog import FAULT_MODELS, PATHS


def resolve_path(path):
    """Expand a paper path ID or copy an explicit sequence, preserving repeated hops."""
    if isinstance(path, str):
        if path not in PATHS:
            raise ValueError(f"unknown path: {path}")
        path = PATHS[path]
    if not isinstance(path, (list, tuple)) or not path:
        raise ValueError("path must be a nonempty list of hop names or a path ID (a-f)")
    if any(not isinstance(name, str) or not name.strip() for name in path):
        raise ValueError("each hop must have a nonempty name")
    return list(path)


def read_path(filename):
    """Read a UTF-8 JSON path ID, hop list, or object with a path field."""
    with Path(filename).open(encoding="utf-8-sig") as stream:
        data = json.load(stream)
    if isinstance(data, dict):
        if "path" not in data:
            raise ValueError("a JSON path object must contain a path field")
        data = data["path"]
    return resolve_path(data)


def target_index(path, hop, occurrence=1):
    """Return the index of the requested visit in an expanded path (visits start at 1)."""
    if not isinstance(hop, str) or not hop.strip():
        raise ValueError("target hop must have a nonempty name")
    if type(occurrence) is not int or occurrence < 1:
        raise ValueError("occurrence must be a positive integer")
    visits = 0
    for index, name in enumerate(path):
        if name == hop:
            visits += 1
            if visits == occurrence:
                return index
    raise ValueError(f"no matching hop {hop!r} at occurrence {occurrence} in path")
