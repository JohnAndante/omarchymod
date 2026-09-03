"""Locate Omarchy and the paths OmarchyMod needs to read or touch."""

import os
from pathlib import Path

# Every Omarchy install has this file; its Lua bootstrap is what a user's
# hyprland.lua dofiles. Presence is a more reliable signal than the package
# database, which misses source checkouts.
_BOOTSTRAP_REL = Path("default") / "hypr" / "bootstrap.lua"


def omarchy_root() -> Path | None:
    """Return Omarchy's install root, or ``None`` when it isn't installed.

    Checks ``$OMARCHY_PATH`` first (the same variable Omarchy's own Lua
    reads), then the packaged location, then a legacy home checkout.
    """
    env = os.environ.get("OMARCHY_PATH")
    candidates = [Path(env)] if env else []
    candidates += _system_candidates()
    for path in candidates:
        if (path / _BOOTSTRAP_REL).is_file():
            return path
    return None


def _system_candidates() -> list[Path]:
    return [Path("/usr/share/omarchy"), Path.home() / ".local/share/omarchy"]


def is_omarchy() -> bool:
    return omarchy_root() is not None


def hypr_config_dir() -> Path:
    return Path.home() / ".config" / "hypr"


def hyprland_entrypoint() -> Path | None:
    """The Hyprland config file Omarchy loads: ``hyprland.lua`` or ``hyprland.conf``."""
    for name in ("hyprland.lua", "hyprland.conf"):
        candidate = hypr_config_dir() / name
        if candidate.is_file():
            return candidate
    return None


def theme_dir() -> Path:
    """Directory Omarchy swaps in on every theme change."""
    return Path.home() / ".local/state/omarchy/current/theme"


def theme_set_hook_dir() -> Path:
    """Drop-in directory run by ``omarchy-hook theme-set``."""
    return Path.home() / ".config/omarchy/hooks/theme-set.d"


def managed_base() -> Path:
    """Suffix-less base path for hyprmod's managed file on Omarchy.

    Under ``hypr/hyprmod/`` on purpose: Omarchy's ``bootstrap.lua`` only
    reloads Lua modules whose name starts with ``default.hypr``, ``hypr``
    or ``omarchy.current.theme``. hyprmod's own default (module
    ``hyprland-gui``) matches none, so a ``hyprctl reload`` would leave
    its edits stale until a full compositor restart. This base resolves
    to module ``hypr.hyprmod.hyprland-gui``, which reloads.
    """
    return hypr_config_dir() / "hyprmod" / "hyprland-gui"
