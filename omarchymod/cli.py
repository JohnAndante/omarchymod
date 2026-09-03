"""``omarchymod`` command line: install, uninstall, status."""

import argparse
import shutil
import sys
from pathlib import Path

from omarchymod import __version__, backup, detect, gtk_theme
from omarchymod.paths import display_path


def _cmd_install(args: argparse.Namespace) -> int:
    root = detect.omarchy_root()
    if root is None:
        print("Omarchy not detected. Nothing to do.", file=sys.stderr)
        return 1

    from omarchymod import integrate

    session = backup.Backup()
    notes: list[str] = []
    try:
        notes += integrate.apply(session)
        if not args.no_gtk:
            notes += gtk_theme.sync(session)
            notes += gtk_theme.install_hook(session)
    except integrate.IntegrationError as err:
        print(f"install failed: {err}", file=sys.stderr)
        print(f"{len(session.changes)} change(s) were recorded; revert with: omarchymod uninstall")
        return 1

    for note in notes:
        print(note)
    print(f"\n{len(session.changes)} change(s) recorded. Revert with: omarchymod uninstall")
    return 0


def _cmd_uninstall(args: argparse.Namespace) -> int:
    if not args.dry_run:
        try:
            from omarchymod import integrate

            for note in integrate.restore():
                print(note)
        except ImportError:
            pass

    report = backup.revert(dry_run=args.dry_run)
    for change in report.reverted:
        verb = "would revert" if args.dry_run else "reverted"
        print(f"{verb} {change.op} {display_path(Path(change.path))}")
    for skip in report.skipped:
        print(
            f"SKIPPED {display_path(Path(skip.change.path))}: {skip.reason}",
            file=sys.stderr,
        )
        if skip.change.backup:
            print(f"        original saved at {skip.change.backup}", file=sys.stderr)

    if not report.reverted and not report.skipped:
        print("Nothing recorded to revert.")

    if args.purge and not args.dry_run:
        if report.skipped:
            print("not purging: some changes were skipped above", file=sys.stderr)
        else:
            for note in _purge():
                print(note)

    return 2 if report.skipped else 0


def _purge() -> list[str]:
    """Remove OmarchyMod's own leftovers after a clean revert.

    The state directory (manifest + backup tree) is kept by a normal
    uninstall as a safety net; ``--purge`` is the opt-in that clears it,
    plus hyprmod's managed file and dir when nothing wrote to them.
    """
    notes: list[str] = []
    managed = detect.managed_base()
    for suffix in (".lua", ".conf"):
        candidate = managed.with_suffix(suffix)
        if candidate.is_file() and candidate.read_text(encoding="utf-8") == "":
            candidate.unlink()
            notes.append(f"removed empty {display_path(candidate)}")
    hyprmod_dir = detect.hypr_config_dir() / "hyprmod"
    if hyprmod_dir.is_dir() and not any(hyprmod_dir.iterdir()):
        hyprmod_dir.rmdir()
        notes.append(f"removed empty {display_path(hyprmod_dir)}")
    if backup.STATE_DIR.exists():
        shutil.rmtree(backup.STATE_DIR)
        notes.append(f"removed {display_path(backup.STATE_DIR)}")
    return notes


def _cmd_status(_args: argparse.Namespace) -> int:
    root = detect.omarchy_root()
    print(f"Omarchy: {'detected at ' + str(root) if root else 'not detected'}")
    entry = detect.hyprland_entrypoint()
    print(f"Hyprland entrypoint: {display_path(entry) if entry else 'none found'}")

    changes = backup.recorded_changes()
    if not changes:
        print("\nNo changes recorded.")
        return 0

    print(f"\n{len(changes)} change(s) recorded:")
    for change in changes:
        drift = "" if backup.matches_disk(change) else "  [drifted]"
        print(f"  {change.op:8} {display_path(Path(change.path))}{drift}")
    return 0


def _cmd_sync_gtk(_args: argparse.Namespace) -> int:
    if not detect.is_omarchy():
        return 0
    for note in gtk_theme.refresh():
        print(note)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omarchymod", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    install = sub.add_parser("install", help="wire hyprmod into Omarchy")
    install.add_argument("--no-gtk", action="store_true", help="skip the gtk.css sync and hook")
    install.set_defaults(func=_cmd_install)

    uninstall = sub.add_parser("uninstall", help="revert every recorded change")
    uninstall.add_argument("--dry-run", action="store_true", help="show what would be reverted")
    uninstall.add_argument(
        "--purge",
        action="store_true",
        help="also delete OmarchyMod's state dir and hyprmod's empty managed file",
    )
    uninstall.set_defaults(func=_cmd_uninstall)

    status = sub.add_parser("status", help="show what OmarchyMod has changed")
    status.set_defaults(func=_cmd_status)

    sync_gtk = sub.add_parser("sync-gtk", help=argparse.SUPPRESS)
    sync_gtk.set_defaults(func=_cmd_sync_gtk)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
