"""Helpers for resolving package resources such as icons and stylesheets."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path


def resource_path(path: str | Path) -> str:
    """Return a filesystem path for a bundled resource or local file.

    Existing absolute or relative paths are returned first. Package resources
    can be requested with paths such as ``ico/folder.png`` or
    ``styles/widgets.qss``.
    """

    raw_path = Path(path)
    if raw_path.exists():
        return str(raw_path)

    normalized = str(path).replace("\\", "/")

    package_root = files(__package__)
    resource = package_root.joinpath(normalized)
    if resource.is_file():
        return str(resource)

    return str(raw_path)


def stylesheet_path(name: str = "widgets.qss") -> str:
    """Return the filesystem path for a bundled QSS stylesheet."""

    return resource_path(f"styles/{name}")


def load_stylesheet(name: str = "widgets.qss") -> str:
    """Read one bundled QSS stylesheet."""

    resource = files(__package__).joinpath("styles", name)
    if not resource.is_file():
        available = ", ".join(available_stylesheets()) or "none"
        raise FileNotFoundError(f"Unknown stylesheet {name!r}. Available stylesheets: {available}")
    return resource.read_text(encoding="utf-8")


def load_stylesheets(*names: str) -> str:
    """Read and join multiple bundled QSS stylesheets.

    When no names are provided, all bundled stylesheets are loaded in sorted
    order. Pass explicit names when order matters.
    """

    selected_names = names or tuple(available_stylesheets())
    return "\n\n".join(load_stylesheet(name) for name in selected_names)


def available_stylesheets() -> list[str]:
    """Return bundled QSS stylesheet names."""

    styles = files(__package__).joinpath("styles")
    if not styles.is_dir():
        return []
    return sorted(resource.name for resource in styles.iterdir() if resource.name.endswith(".qss"))
