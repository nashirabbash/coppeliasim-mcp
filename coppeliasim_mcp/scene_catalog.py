"""Searchable catalog of CoppeliaSim model (.ttm) and scene (.ttt) files."""

from pathlib import Path

from .json_log import log
from .runner import COPPELIA_ROOT, ROBOT_ALIASES

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


def resolve_model_path(name: str) -> Path:
    """Resolve robot alias or path to an absolute .ttm model path."""
    name_clean = name.strip().lower()
    if name_clean in ROBOT_ALIASES:
        rel = ROBOT_ALIASES[name_clean]
        p = COPPELIA_ROOT / "models" / rel
        if p.exists():
            return p

    # Try direct relative path under models/
    candidate = COPPELIA_ROOT / "models" / name
    if candidate.exists():
        return candidate
    candidate_ttm = COPPELIA_ROOT / "models" / f"{name}.ttm"
    if candidate_ttm.exists():
        return candidate_ttm

    # Direct absolute path
    p = Path(name)
    if p.exists():
        return p

    raise FileNotFoundError(f"Robot model '{name}' not found. Available aliases: {list(ROBOT_ALIASES.keys())}")


def make_load_robot_fn(sim):
    """Factory creating the load_robot helper injected into agent code."""
    def load_robot(name: str, position: list = None, orientation: list = None):
        model_path = resolve_model_path(name)
        handle = sim.loadModel(str(model_path))
        if position is not None:
            sim.setObjectPosition(handle, -1, position)
        if orientation is not None:
            sim.setObjectOrientation(handle, -1, orientation)
        return handle
    return load_robot
