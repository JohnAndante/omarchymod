"""Backup, manifest, and precise revert for every file OmarchyMod touches.

Nothing shared with Omarchy or the user is mutated without a copy of the
original landing under ``backups/<timestamp>/`` and a manifest entry that
:func:`revert` can later undo. Each change is flushed to the manifest as
it happens, so a run that dies halfway still leaves a manifest that
describes exactly what reached disk.

A revert only touches a file that still matches what we wrote (its
recorded ``hash_after``). Anything edited since is left alone and
reported, never clobbered.
"""

import hashlib
import json
import os
import shutil
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from omarchymod.paths import atomic_write

STATE_DIR = Path.home() / ".local" / "state" / "omarchymod"

MANIFEST_VERSION = 1

OP_CREATE = "create"
OP_APPEND = "append"
OP_REPLACE = "replace"
OP_SYMLINK = "symlink"


class BackupError(Exception):
    """A backup could not be taken, so the mutation was not attempted."""


@dataclass(slots=True, frozen=True)
class Change:
    timestamp: str
    path: str
    op: str
    hash_before: str | None
    hash_after: str | None
    backup: str | None
    detail: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class SkippedChange:
    change: Change
    reason: str


@dataclass(slots=True, frozen=True)
class RevertReport:
    reverted: list[Change]
    skipped: list[SkippedChange]


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def _manifest_path() -> Path:
    return STATE_DIR / "manifest.json"


def _backups_dir() -> Path:
    return STATE_DIR / "backups"


# ---------------------------------------------------------------------------
# State identity
# ---------------------------------------------------------------------------


def _state_id(path: Path) -> str | None:
    """Stable id for whatever is at *path*: a content hash, a link target, or ``None``.

    ``None`` means nothing is there. A symlink reports its target, not the
    content it points at, so retargeting it counts as a change.
    """
    if path.is_symlink():
        return "symlink:" + os.readlink(path)
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _relanchor(path: Path) -> Path:
    """``/home/u/.config/f`` -> ``home/u/.config/f`` so it can nest under a dir."""
    return path.relative_to(path.anchor)


def _unique_run_dir(stamp: str) -> Path:
    """A backup dir for this run. Second-granularity stamps can repeat, so bump."""
    root = _backups_dir() / stamp
    suffix = 2
    while root.exists():
        root = _backups_dir() / f"{stamp}#{suffix}"
        suffix += 1
    return root


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


def load_manifest() -> dict[str, object]:
    """Return the on-disk manifest, or an empty one when there is none."""
    path = _manifest_path()
    if not path.is_file():
        return {"version": MANIFEST_VERSION, "changes": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "changes" not in data:
        raise BackupError(f"manifest at {path} is not readable")
    return data


def _dumps(manifest: dict[str, object]) -> str:
    return json.dumps(manifest, indent=2) + "\n"


def _manifest_changes(manifest: dict[str, object]) -> list[dict[str, object]]:
    raw = manifest.get("changes", [])
    if not isinstance(raw, list):
        raise BackupError("manifest 'changes' is not a list")
    return [entry for entry in raw if isinstance(entry, dict)]


def _append_change(change: Change) -> None:
    manifest = load_manifest()
    changes = _manifest_changes(manifest)
    changes.append(asdict(change))
    manifest["changes"] = changes
    atomic_write(_manifest_path(), _dumps(manifest))


def _opt_str(value: object) -> str | None:
    return None if value is None else str(value)


def _str_dict(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(val) for key, val in value.items()}


def _change_from_dict(entry: dict[str, object]) -> Change:
    return Change(
        timestamp=str(entry.get("timestamp", "")),
        path=str(entry["path"]),
        op=str(entry["op"]),
        hash_before=_opt_str(entry.get("hash_before")),
        hash_after=_opt_str(entry.get("hash_after")),
        backup=_opt_str(entry.get("backup")),
        detail=_str_dict(entry.get("detail", {})),
    )


def recorded_changes() -> list[Change]:
    """Every change OmarchyMod has recorded, oldest first."""
    return [_change_from_dict(entry) for entry in _manifest_changes(load_manifest())]


def matches_disk(change: Change) -> bool:
    """True when the file still holds exactly what this change wrote."""
    return _state_id(Path(change.path)) == change.hash_after


# ---------------------------------------------------------------------------
# Recording new changes
# ---------------------------------------------------------------------------


class Backup:
    """One OmarchyMod run's set of file mutations.

    Every method backs the target up first, performs the change through an
    atomic write, and flushes a manifest entry before returning.
    """

    def __init__(self) -> None:
        self._stamp = _utc_stamp()
        self._root = _unique_run_dir(self._stamp)
        self._changes: list[Change] = []

    @property
    def changes(self) -> list[Change]:
        return list(self._changes)

    def write(self, path: Path, content: str, *, detail: dict[str, str] | None = None) -> None:
        """Create *path*, or replace its contents, keeping a copy of any original."""
        before = _state_id(path)
        stash = self._stash(path)
        atomic_write(path, content)
        op = OP_REPLACE if before is not None else OP_CREATE
        self._record(path, op, before, stash, detail or {})

    def append_block(self, path: Path, block: str, *, marker: str) -> bool:
        """Append *block* to *path* once. No-op (``False``) when *marker* is already present."""
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
        if marker in existing:
            return False
        before = _state_id(path)
        stash = self._stash(path)
        head = existing if not existing or existing.endswith("\n") else existing + "\n"
        atomic_write(path, head + block)
        op = OP_APPEND if before is not None else OP_CREATE
        self._record(path, op, before, stash, {"marker": marker})
        return True

    def symlink(self, link: Path, target: Path, *, detail: dict[str, str] | None = None) -> None:
        """Point *link* at *target*, keeping a copy of whatever *link* was."""
        before = _state_id(link)
        stash = self._stash(link)
        link.parent.mkdir(parents=True, exist_ok=True)
        tmp = link.with_name(f".omarchymod-{link.name}.tmp")
        tmp.unlink(missing_ok=True)
        tmp.symlink_to(target)
        os.replace(tmp, link)
        merged = {"target": str(target), **(detail or {})}
        self._record(link, OP_SYMLINK, before, stash, merged)

    @contextmanager
    def external_edit(self, path: Path, *, detail: dict[str, str] | None = None) -> Iterator[None]:
        """Record a change some other code makes to *path* inside the block.

        Used to wrap a call into hyprmod's own setup, which writes the
        user's entrypoint itself. We snapshot and back up before, then
        record the diff after so :func:`revert` can undo it.
        """
        before = _state_id(path)
        stash = self._stash(path)
        try:
            yield
        finally:
            if _state_id(path) != before:
                op = OP_REPLACE if before is not None else OP_CREATE
                self._record(path, op, before, stash, detail or {})

    def _stash(self, path: Path) -> str | None:
        if not path.is_symlink() and not path.exists():
            return None
        dest = self._root / _relanchor(path)
        if dest.exists() or dest.is_symlink():
            raise BackupError(f"a backup for {path} already exists this run at {dest}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            dest.symlink_to(os.readlink(path))
        else:
            shutil.copy2(path, dest)
        return str(dest)

    def _record(
        self,
        path: Path,
        op: str,
        before: str | None,
        stash: str | None,
        detail: dict[str, str],
    ) -> None:
        change = Change(
            timestamp=self._stamp,
            path=str(path),
            op=op,
            hash_before=before,
            hash_after=_state_id(path),
            backup=stash,
            detail=detail,
        )
        self._changes.append(change)
        _append_change(change)


def note_refresh(path: Path) -> None:
    """Repoint the newest manifest entry for *path* at its current state.

    The theme-set hook rewrites files OmarchyMod already owns. Without
    this, the drift would make a later :func:`revert` refuse to remove
    them.
    """
    manifest = load_manifest()
    changes = _manifest_changes(manifest)
    current = _state_id(path)
    for entry in reversed(changes):
        if entry.get("path") == str(path):
            entry["hash_after"] = current
            manifest["changes"] = changes
            atomic_write(_manifest_path(), _dumps(manifest))
            return


# ---------------------------------------------------------------------------
# Revert
# ---------------------------------------------------------------------------


def revert(*, dry_run: bool = False) -> RevertReport:
    """Undo every recorded change, newest first.

    A change whose file no longer matches its ``hash_after`` is skipped
    and kept in the manifest; everything reverted is dropped from it.
    """
    manifest = load_manifest()
    entries = _manifest_changes(manifest)
    reverted: list[Change] = []
    skipped: list[SkippedChange] = []
    kept: list[dict[str, object]] = []

    for entry in reversed(entries):
        change = _change_from_dict(entry)
        current = _state_id(Path(change.path))
        if current == change.hash_after:
            if not dry_run:
                _apply_revert(change)
            reverted.append(change)
        elif current is None:
            # Already gone. Nothing to undo, nothing to preserve.
            reverted.append(change)
        else:
            skipped.append(
                SkippedChange(change=change, reason="modified since OmarchyMod wrote it")
            )
            kept.append(entry)

    if not dry_run:
        manifest["changes"] = list(reversed(kept))
        atomic_write(_manifest_path(), _dumps(manifest))
    return RevertReport(reverted=reverted, skipped=skipped)


def _apply_revert(change: Change) -> None:
    path = Path(change.path)
    if change.backup is None:
        if path.is_symlink() or path.exists():
            path.unlink()
        return
    backup = Path(change.backup)
    if backup.is_symlink():
        target = os.readlink(backup)
        tmp = path.with_name(f".omarchymod-{path.name}.tmp")
        tmp.unlink(missing_ok=True)
        tmp.symlink_to(target)
        os.replace(tmp, path)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            path.unlink()
        shutil.copy2(backup, path)
