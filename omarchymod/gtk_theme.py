"""Keep libadwaita apps on the active Omarchy theme.

Omarchy ships a ``gtk.css`` in every theme but never installs it where
libadwaita looks. libadwaita ignores ``gtk-theme`` by design and only
honours ``@define-color`` overrides in ``~/.config/gtk-4.0/gtk.css`` (see
basecamp/omarchy#7557), so without this every GTK4 app, hyprmod included,
renders as stock Adwaita against a themed desktop.

We copy the theme's file into ``gtk-4.0`` and ``gtk-3.0`` and drop a
``theme-set`` hook that re-copies it on every theme change. The hook only
ever rewrites a file OmarchyMod already owns.
"""

from pathlib import Path

from omarchymod import detect
from omarchymod.backup import Backup, note_refresh
from omarchymod.paths import atomic_write, display_path

HOOK_NAME = "omarchymod-gtk"
_MARKER = "omarchymod managed"
_HEADER = f"/* {_MARKER}: copied from Omarchy's active theme; edits are lost on theme change. */\n"

_HOOK_BODY = f"""\
#!/bin/bash
# {_MARKER}: re-copy the active theme's gtk.css into ~/.config/gtk-4.0 and gtk-3.0.
exec omarchymod sync-gtk
"""


def gtk4_css() -> Path:
    return Path.home() / ".config" / "gtk-4.0" / "gtk.css"


def gtk3_css() -> Path:
    return Path.home() / ".config" / "gtk-3.0" / "gtk.css"


def _targets() -> tuple[Path, Path]:
    return gtk4_css(), gtk3_css()


def theme_gtk_css() -> Path | None:
    """The active theme's ``gtk.css``, when it ships one."""
    css = detect.theme_dir() / "gtk.css"
    return css if css.is_file() else None


def _payload(source: Path) -> str:
    return _HEADER + source.read_text(encoding="utf-8")


def _owned_by_us(path: Path) -> bool:
    return path.is_file() and _MARKER in path.read_text(encoding="utf-8")


def sync(backup: Backup) -> list[str]:
    """Copy the theme's gtk.css into the GTK config dirs. Idempotent."""
    source = theme_gtk_css()
    if source is None:
        return [f"no gtk.css in {display_path(detect.theme_dir())}, skipped"]
    payload = _payload(source)
    notes: list[str] = []
    for target in _targets():
        if target.is_file() and target.read_text(encoding="utf-8") == payload:
            notes.append(f"{display_path(target)} already current")
            continue
        if target.is_file() and not _owned_by_us(target):
            notes.append(f"replacing your existing {display_path(target)} (backed up)")
        backup.write(target, payload, detail={"source": str(source)})
        notes.append(f"synced {display_path(target)}")
    return notes


def refresh() -> list[str]:
    """Hook entry point: re-copy the theme's gtk.css over the files we own.

    Never creates or overwrites a file OmarchyMod does not already own, so
    running from a theme-set hook can't surprise anyone.
    """
    source = theme_gtk_css()
    if source is None:
        return ["no theme gtk.css to sync"]
    payload = _payload(source)
    notes: list[str] = []
    for target in _targets():
        if not _owned_by_us(target):
            continue
        atomic_write(target, payload)
        note_refresh(target)
        notes.append(f"refreshed {display_path(target)}")
    return notes


def install_hook(backup: Backup) -> list[str]:
    hook = detect.theme_set_hook_dir() / HOOK_NAME
    if hook.is_file() and hook.read_text(encoding="utf-8") == _HOOK_BODY:
        return [f"{display_path(hook)} already installed"]
    backup.write(hook, _HOOK_BODY, detail={"kind": "theme-set hook"})
    hook.chmod(0o755)
    return [f"installed {display_path(hook)}"]
