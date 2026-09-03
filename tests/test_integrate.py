from pathlib import Path

import pytest

from omarchymod import integrate


@pytest.fixture(autouse=True)
def lua_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / ".config"
    monkeypatch.setattr(integrate, "_LUA_ROOT", root)
    return root


def test_lua_module_resolves_under_config_not_hypr(lua_root: Path) -> None:
    managed = lua_root / "hypr" / "hyprmod" / "hyprland-gui.lua"
    # Must be require("hypr.hyprmod.hyprland-gui"): Omarchy's package.path is
    # rooted at ~/.config, so a bare "hyprmod.hyprland-gui" would not resolve.
    assert integrate._lua_module(managed) == "hypr.hyprmod.hyprland-gui"


class TestIncludeBlock:
    def test_lua_entry_gets_a_require_line(self, lua_root: Path) -> None:
        entry = lua_root / "hypr" / "hyprland.lua"
        managed = lua_root / "hypr" / "hyprmod" / "hyprland-gui.lua"
        block = integrate._include_block(entry, managed)
        assert 'require("hypr.hyprmod.hyprland-gui")' in block
        assert integrate._MARKER in block

    def test_conf_entry_gets_an_absolute_source_line(self, lua_root: Path) -> None:
        entry = lua_root / "hypr" / "hyprland.conf"
        managed = lua_root / "hypr" / "hyprmod" / "hyprland-gui.conf"
        block = integrate._include_block(entry, managed)
        assert f"source = {managed}" in block
        assert block.lstrip().startswith("#")
