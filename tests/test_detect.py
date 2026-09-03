from pathlib import Path

import pytest

from omarchymod import detect


def _make_omarchy_tree(root: Path) -> Path:
    bootstrap = root / "default" / "hypr" / "bootstrap.lua"
    bootstrap.parent.mkdir(parents=True)
    bootstrap.write_text("-- bootstrap\n")
    return root


class TestOmarchyRoot:
    def test_honours_omarchy_path_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = _make_omarchy_tree(tmp_path / "opt-omarchy")
        monkeypatch.setenv("OMARCHY_PATH", str(root))
        monkeypatch.setattr(detect, "_system_candidates", list)
        assert detect.omarchy_root() == root
        assert detect.is_omarchy() is True

    def test_none_when_not_installed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OMARCHY_PATH", raising=False)
        monkeypatch.setattr(detect, "_system_candidates", list)
        assert detect.omarchy_root() is None
        assert detect.is_omarchy() is False

    def test_falls_back_to_system_candidate(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = _make_omarchy_tree(tmp_path / "usr-share-omarchy")
        monkeypatch.delenv("OMARCHY_PATH", raising=False)
        monkeypatch.setattr(detect, "_system_candidates", lambda: [root])
        assert detect.omarchy_root() == root


class TestEntrypoint:
    def test_prefers_lua_over_conf(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        hypr = tmp_path / "hypr"
        hypr.mkdir()
        (hypr / "hyprland.conf").write_text("")
        (hypr / "hyprland.lua").write_text("")
        monkeypatch.setattr(detect, "hypr_config_dir", lambda: hypr)
        assert detect.hyprland_entrypoint() == hypr / "hyprland.lua"

    def test_none_when_no_entrypoint(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(detect, "hypr_config_dir", lambda: tmp_path)
        assert detect.hyprland_entrypoint() is None


def test_managed_base_lands_under_hypr_hyprmod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(detect, "hypr_config_dir", lambda: Path("/home/x/.config/hypr"))
    assert detect.managed_base() == Path("/home/x/.config/hypr/hyprmod/hyprland-gui")
