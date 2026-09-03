import json
from pathlib import Path

import pytest

from omarchymod import backup


@pytest.fixture
def state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "state"
    monkeypatch.setattr(backup, "STATE_DIR", root)
    return root


def _manifest_ops(state: Path) -> list[str]:
    data = json.loads((state / "manifest.json").read_text())
    return [entry["op"] for entry in data["changes"]]


class TestWrite:
    def test_create_records_no_backup(self, state: Path, tmp_path: Path) -> None:
        target = tmp_path / "sub" / "new.conf"
        session = backup.Backup()
        session.write(target, "hello\n")

        assert target.read_text() == "hello\n"
        (change,) = session.changes
        assert change.op == backup.OP_CREATE
        assert change.hash_before is None
        assert change.backup is None

    def test_replace_backs_up_original(self, state: Path, tmp_path: Path) -> None:
        target = tmp_path / "f.conf"
        target.write_text("original\n")

        session = backup.Backup()
        session.write(target, "replaced\n")

        (change,) = session.changes
        assert change.op == backup.OP_REPLACE
        assert change.backup is not None
        assert Path(change.backup).read_text() == "original\n"

    def test_manifest_flushed_per_change(self, state: Path, tmp_path: Path) -> None:
        session = backup.Backup()
        session.write(tmp_path / "a", "a")
        session.write(tmp_path / "b", "b")
        assert _manifest_ops(state) == ["create", "create"]

    def test_two_runs_keep_separate_backups(self, state: Path, tmp_path: Path) -> None:
        target = tmp_path / "f"
        target.write_text("v1\n")
        backup.Backup().write(target, "v2\n")
        backup.Backup().write(target, "v3\n")

        saved = sorted(p.read_text() for p in (state / "backups").rglob("f"))
        assert saved == ["v1\n", "v2\n"]


class TestAppendBlock:
    def test_appends_once(self, state: Path, tmp_path: Path) -> None:
        target = tmp_path / "hyprland.lua"
        target.write_text("require('hypr.monitors')\n")

        session = backup.Backup()
        added = session.append_block(target, "-- m\nrequire('x')\n", marker="-- m")
        assert added is True
        assert target.read_text().endswith("-- m\nrequire('x')\n")

        again = backup.Backup().append_block(target, "-- m\nrequire('x')\n", marker="-- m")
        assert again is False

    def test_adds_trailing_newline_before_block(self, state: Path, tmp_path: Path) -> None:
        target = tmp_path / "f"
        target.write_text("no-newline")
        backup.Backup().append_block(target, "BLOCK\n", marker="BLOCK")
        assert target.read_text() == "no-newline\nBLOCK\n"


class TestExternalEdit:
    def test_records_edit_made_inside_block(self, state: Path, tmp_path: Path) -> None:
        target = tmp_path / "entry.lua"
        target.write_text("before\n")

        session = backup.Backup()
        with session.external_edit(target, detail={"via": "other-tool"}):
            target.write_text("before\nafter\n")

        (change,) = session.changes
        assert change.op == backup.OP_REPLACE
        assert Path(change.backup or "").read_text() == "before\n"

    def test_no_record_when_nothing_changed(self, state: Path, tmp_path: Path) -> None:
        target = tmp_path / "entry.lua"
        target.write_text("same\n")

        session = backup.Backup()
        with session.external_edit(target):
            pass
        assert session.changes == []

    def test_records_even_when_body_raises(self, state: Path, tmp_path: Path) -> None:
        target = tmp_path / "entry.lua"
        target.write_text("before\n")

        session = backup.Backup()
        with pytest.raises(RuntimeError):
            with session.external_edit(target):
                target.write_text("half\n")
                raise RuntimeError("boom")
        assert [c.op for c in session.changes] == [backup.OP_REPLACE]


class TestRevert:
    def test_restores_and_clears_manifest(self, state: Path, tmp_path: Path) -> None:
        existing = tmp_path / "existing"
        existing.write_text("orig\n")
        created = tmp_path / "created"

        session = backup.Backup()
        session.write(existing, "changed\n")
        session.write(created, "new\n")

        report = backup.revert()

        assert existing.read_text() == "orig\n"
        assert not created.exists()
        assert {c.op for c in report.reverted} == {"replace", "create"}
        assert backup.recorded_changes() == []

    def test_skips_a_file_changed_since(self, state: Path, tmp_path: Path) -> None:
        target = tmp_path / "f"
        target.write_text("orig\n")
        backup.Backup().write(target, "ours\n")

        target.write_text("user touched this\n")
        report = backup.revert()

        assert target.read_text() == "user touched this\n"
        assert len(report.skipped) == 1
        assert len(backup.recorded_changes()) == 1

    def test_gone_file_is_dropped_not_skipped(self, state: Path, tmp_path: Path) -> None:
        target = tmp_path / "f"
        backup.Backup().write(target, "new\n")
        target.unlink()

        report = backup.revert()
        assert report.skipped == []
        assert backup.recorded_changes() == []

    def test_dry_run_changes_nothing(self, state: Path, tmp_path: Path) -> None:
        target = tmp_path / "f"
        target.write_text("orig\n")
        backup.Backup().write(target, "ours\n")

        report = backup.revert(dry_run=True)
        assert target.read_text() == "ours\n"
        assert len(report.reverted) == 1
        assert len(backup.recorded_changes()) == 1

    def test_reverts_newest_first(self, state: Path, tmp_path: Path) -> None:
        target = tmp_path / "f"
        target.write_text("v0\n")
        backup.Backup().write(target, "v1\n")
        backup.Backup().write(target, "v2\n")

        backup.revert()
        assert target.read_text() == "v0\n"

    def test_symlink_revert_removes_link_when_nothing_was_there(
        self, state: Path, tmp_path: Path
    ) -> None:
        link = tmp_path / "link"
        dest = tmp_path / "dest"
        dest.write_text("x\n")

        backup.Backup().symlink(link, dest)
        assert link.is_symlink()

        backup.revert()
        assert not link.is_symlink() and not link.exists()

    def test_empty_manifest_reverts_to_nothing(self, state: Path) -> None:
        report = backup.revert()
        assert report.reverted == [] and report.skipped == []


class TestNoteRefresh:
    def test_keeps_revert_working_after_our_own_rewrite(self, state: Path, tmp_path: Path) -> None:
        target = tmp_path / "gtk.css"
        backup.Backup().write(target, "v1\n")

        target.write_text("v2 from a later theme change\n")
        backup.note_refresh(target)

        report = backup.revert()
        assert not target.exists()
        assert report.skipped == []
