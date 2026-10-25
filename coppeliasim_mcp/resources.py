"""Paths to bundled launch resources in source checkouts and installations."""

from pathlib import Path
import sysconfig


def resource_path(*parts: str) -> Path:
    checkout = Path(__file__).resolve().parent.parent.joinpath(*parts)
    if checkout.exists():
        return checkout
    return Path(sysconfig.get_path("data"), "share", "coppeliasim-mcp", *parts)
