from pathlib import Path

import pytest

from omarchymod import backup, cli, detect


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(backup, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(detect, "hypr_config_dir", lambda: tmp_path / ".config" / "hypr")
    return tmp_path


class TestPurge:
    def test_removes_state_and_empty_managed_file(self, env: Path) -> None:
        (env / "state").mkdir()
        (env / "state" / "manifest.json").write_text("{}")
        managed = env / ".config" / "hypr" / "hyprmod" / "hyprland-gui.lua"
        managed.parent.mkdir(parents=True)
        managed.write_text("")

        cli._purge()

        assert not (env / "state").exists()
        assert not managed.exists()
        assert not managed.parent.exists()

    def test_keeps_managed_file_that_has_content(self, env: Path) -> None:
        managed = env / ".config" / "hypr" / "hyprmod" / "hyprland-gui.lua"
        managed.parent.mkdir(parents=True)
        managed.write_text("general { gaps_in = 3 }\n")

        cli._purge()

        assert managed.read_text() == "general { gaps_in = 3 }\n"
