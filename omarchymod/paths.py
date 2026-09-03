"""Path helpers shared across the package."""

import os
import tempfile
from pathlib import Path


def display_path(path: Path) -> str:
    """Return *path* with the home directory collapsed to ``~``."""
    try:
        return "~/" + str(Path(path).relative_to(Path.home()))
    except ValueError:
        return str(path)


def atomic_write(path: Path, content: str) -> None:
    """Write *content* to *path* via a temp file + rename in the same directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".omarchymod-", suffix=".tmp")
    tmp_path = Path(tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
