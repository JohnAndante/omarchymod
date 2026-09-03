"""Wire hyprmod's managed config into Omarchy's Hyprland setup.

Two things hyprmod does not do for itself on Omarchy:

1. Its managed file has to sit where Hyprland's Lua loader will reload it.
   Omarchy's ``bootstrap.lua`` only clears ``package.loaded`` for modules
   under ``default.hypr``, ``hypr`` or ``omarchy.current.theme``, and its
   ``package.path`` is rooted at ``~/.config`` (not ``~/.config/hypr``).
   So the file goes at ``~/.config/hypr/hyprmod/hyprland-gui.lua`` and the
   include is ``require("hypr.hyprmod.hyprland-gui")`` -- which both
   resolves and reloads. hyprmod's own ``setup`` module computes the
   module name against a different ``package.path`` and would emit a line
   that never loads here, so OmarchyMod writes the include itself.
2. Its GUI reads the managed path from a ``config-path`` GSetting. We
   point that at the same file.

Everything hyprmod-specific is imported lazily so ``status`` /
``uninstall`` / ``sync-gtk`` never pull in GTK.
"""

from pathlib import Path

from omarchymod import detect
from omarchymod.backup import STATE_DIR, Backup
from omarchymod.paths import display_path

_MARKER = "omarchymod managed"
_PREV_CONFIG_PATH = STATE_DIR / "hyprmod-config-path.prev"

# Lua's package.path on Omarchy resolves module "a.b" against ~/.config,
# not against the entrypoint's own directory.
_LUA_ROOT = Path.home() / ".config"


class IntegrationError(Exception):
    """The hyprmod wiring could not be completed."""


def _lua_module(managed_file: Path) -> str:
    return ".".join(managed_file.with_suffix("").relative_to(_LUA_ROOT).parts)


def _include_block(entry: Path, managed_file: Path) -> str:
    if entry.suffix == ".lua":
        line = f'require("{_lua_module(managed_file)}")'
        comment = f"-- {_MARKER}: load hyprmod's GUI settings"
    else:
        line = f"source = {managed_file}"
        comment = f"# {_MARKER}: load hyprmod's GUI settings"
    return f"\n{comment}\n{line}\n"


def apply(backup: Backup) -> list[str]:
    """Point hyprmod at the Omarchy-safe managed path and add its include line."""
    from gi.repository import Gio
    from hyprmod.core import settings as hm_settings

    entry = detect.hyprland_entrypoint()
    if entry is None:
        raise IntegrationError(
            f"no hyprland.lua or hyprland.conf in {display_path(detect.hypr_config_dir())}"
        )

    settings = hm_settings.open_settings()
    if settings is None:
        raise IntegrationError("hyprmod's GSettings schema could not be opened")

    notes: list[str] = []
    base = detect.managed_base()
    managed_file = base.with_suffix(".lua" if entry.suffix == ".lua" else ".conf")

    if settings.get_string("config-path") != str(base):
        if not _PREV_CONFIG_PATH.exists():
            previous = settings.get_string("config-path")
            backup.write(_PREV_CONFIG_PATH, previous + "\n", detail={"key": "config-path"})
        settings.set_string("config-path", str(base))
        Gio.Settings.sync()
        notes.append(f"pointed hyprmod's config-path at {display_path(base)}")

    if not managed_file.exists():
        backup.write(managed_file, "", detail={"owner": "hyprmod"})
        notes.append(f"created hyprmod managed file {display_path(managed_file)}")

    if backup.append_block(entry, _include_block(entry, managed_file), marker=_MARKER):
        notes.append(f"added hyprmod include to {display_path(entry)}")
    else:
        notes.append(f"hyprmod include already in {display_path(entry)}")
    return notes


def restore() -> list[str]:
    """Reset hyprmod's ``config-path`` GSetting to its pre-install value.

    Called before :func:`omarchymod.backup.revert`, which then removes the
    saved-value file itself. Best-effort: hyprmod may already be gone.
    """
    if not _PREV_CONFIG_PATH.is_file():
        return []
    previous = _PREV_CONFIG_PATH.read_text(encoding="utf-8").strip()
    try:
        from gi.repository import Gio
        from hyprmod.core import settings as hm_settings
    except ImportError:
        return [f"could not reset hyprmod's config-path (hyprmod gone); it was {previous!r}"]
    settings = hm_settings.open_settings()
    if settings is None:
        return ["could not open hyprmod's GSettings to reset config-path"]
    settings.set_string("config-path", previous)
    Gio.Settings.sync()
    return [f"reset hyprmod's config-path to {previous!r}"]
