from pathlib import Path

import pytest

from omarchymod import backup, detect, gtk_theme


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    monkeypatch.setattr(backup, "STATE_DIR", tmp_path / "state")

    theme = tmp_path / "theme"
    theme.mkdir()
    (theme / "gtk.css").write_text("@define-color window_bg_color #111111;\n")
    monkeypatch.setattr(detect, "theme_dir", lambda: theme)

    hooks = tmp_path / "hooks"
    monkeypatch.setattr(detect, "theme_set_hook_dir", lambda: hooks)

    gtk4 = tmp_path / "gtk-4.0" / "gtk.css"
    gtk3 = tmp_path / "gtk-3.0" / "gtk.css"
    monkeypatch.setattr(gtk_theme, "gtk4_css", lambda: gtk4)
    monkeypatch.setattr(gtk_theme, "gtk3_css", lambda: gtk3)

    return {"theme": theme, "gtk4": gtk4, "gtk3": gtk3, "hooks": hooks}


class TestSync:
    def test_writes_wrapped_payload_to_both(self, env: dict[str, Path]) -> None:
        gtk_theme.sync(backup.Backup())
        for key in ("gtk4", "gtk3"):
            text = env[key].read_text()
            assert "omarchymod managed" in text
            assert "@define-color window_bg_color #111111;" in text

    def test_warns_when_replacing_a_foreign_file(self, env: dict[str, Path]) -> None:
        env["gtk4"].parent.mkdir(parents=True)
        env["gtk4"].write_text("/* my own tweaks */\n")

        notes = gtk_theme.sync(backup.Backup())

        assert any("replacing your existing" in n for n in notes)
        assert len(backup.recorded_changes()) == 2
        replaced = next(c for c in backup.recorded_changes() if c.path == str(env["gtk4"]))
        assert Path(replaced.backup or "").read_text() == "/* my own tweaks */\n"

    def test_is_idempotent(self, env: dict[str, Path]) -> None:
        gtk_theme.sync(backup.Backup())
        first = len(backup.recorded_changes())

        notes = gtk_theme.sync(backup.Backup())

        assert len(backup.recorded_changes()) == first
        assert all("already current" in n for n in notes)

    def test_skips_when_theme_has_no_gtk_css(
        self, env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (env["theme"] / "gtk.css").unlink()
        notes = gtk_theme.sync(backup.Backup())
        assert notes == [f"no gtk.css in {gtk_theme.display_path(env['theme'])}, skipped"]
        assert not env["gtk4"].exists()


class TestRefresh:
    def test_only_touches_files_we_own(self, env: dict[str, Path]) -> None:
        gtk_theme.sync(backup.Backup())
        env["gtk3"].write_text("/* user took this over */\n")
        (env["theme"] / "gtk.css").write_text("@define-color window_bg_color #222222;\n")

        gtk_theme.refresh()

        assert "#222222" in env["gtk4"].read_text()
        assert env["gtk3"].read_text() == "/* user took this over */\n"

    def test_updates_manifest_so_revert_still_removes_our_file(self, env: dict[str, Path]) -> None:
        gtk_theme.sync(backup.Backup())
        (env["theme"] / "gtk.css").write_text("@define-color window_bg_color #333333;\n")
        gtk_theme.refresh()

        report = backup.revert()
        assert not env["gtk4"].exists()
        assert not env["gtk3"].exists()
        assert report.skipped == []


class TestInstallHook:
    def test_writes_executable_hook(self, env: dict[str, Path]) -> None:
        gtk_theme.install_hook(backup.Backup())
        hook = env["hooks"] / gtk_theme.HOOK_NAME
        assert "omarchymod sync-gtk" in hook.read_text()
        assert hook.stat().st_mode & 0o111
