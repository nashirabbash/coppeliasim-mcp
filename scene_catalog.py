"""Searchable catalog of CoppeliaSim model (.ttm) and scene (.ttt) files."""

from pathlib import Path

from json_log import log
from runner import COPPELIA_ROOT, ROBOT_ALIASES

KIND_DIRS = {"model": ("models", ".ttm"), "scene": ("scenes", ".ttt")}
ALIAS_BY_REL = {(Path("models") / rel).as_posix(): alias for alias, rel in ROBOT_ALIASES.items()}


def iter_entries(root: Path, kind: str):
    folder, suffix = KIND_DIRS[kind]
    for path in sorted((root / folder).rglob(f"*{suffix}")):
        rel = path.relative_to(root).as_posix()
        yield {
            "kind": kind,
            "name": path.stem,
            "path": str(path),
            "relative": rel,
            "alias": ALIAS_BY_REL.get(rel),
        }


def matches(entry: dict, terms: list[str]) -> bool:
    haystack = f"{entry['relative']} {entry['alias'] or ''}".lower()
    return all(term in haystack for term in terms)


def search_catalog(query: str = "", kind: str = "all", limit: int = 50, root: Path = COPPELIA_ROOT) -> dict:
    if kind != "all" and kind not in KIND_DIRS:
        raise ValueError(f"Unsupported catalog kind: {kind}")
    if limit < 1:
        raise ValueError("limit must be at least 1")
    kinds = list(KIND_DIRS) if kind == "all" else [kind]
    terms = query.lower().split()
    found = [entry for k in kinds for entry in iter_entries(root, k) if matches(entry, terms)]
    log("info", "catalog.searched", query=query, kind=kind, total=len(found))
    return {"total": len(found), "results": found[:limit]}
