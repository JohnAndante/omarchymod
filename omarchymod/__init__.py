"""OmarchyMod: companion layer that wires hyprmod into an Omarchy install."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("omarchymod")
except PackageNotFoundError:  # running from a source tree with no install
    __version__ = "0.0.0+source"
