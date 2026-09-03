# Changelog

All notable changes to OmarchyMod will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-03

First release. Wires the [hyprmod](https://github.com/BlueManCZ/hyprmod)
settings app into an Omarchy install so its edits survive a reload and its
window matches the active theme.

### Added

- `omarchymod install`: points hyprmod's `config-path` GSetting at
  `~/.config/hypr/hyprmod/hyprland-gui` and adds
  `require("hypr.hyprmod.hyprland-gui")` to `hyprland.lua`. The module name is
  written directly rather than via hyprmod's own setup, because Omarchy's
  `package.path` is rooted at `~/.config` and hyprmod would emit a line that
  never resolves.
- gtk.css sync: copies the active theme's `gtk.css` into `~/.config/gtk-4.0`
  and `gtk-3.0` so libadwaita apps stop rendering as stock Adwaita, plus a
  `theme-set.d` hook (`omarchymod sync-gtk`) that refreshes it on theme change.
  The hook only ever rewrites a file OmarchyMod already owns.
- Backup layer: every touched file is copied to
  `~/.local/state/omarchymod/backups/<timestamp>/` and recorded in a manifest
  before it is changed. `omarchymod uninstall` reverts each change and skips,
  without overwriting, any file that was edited since. `--purge` also clears
  OmarchyMod's state directory and hyprmod's empty managed file.
- `omarchymod status` and `omarchymod --version`.

### Known issues

- Using hyprmod's monitor editor can make Omarchy's `omarchy-hyprland-monitor-watch`
  rewrite `~/.config/hypr/monitors.lua`. This is outside the backup layer's
  coverage because OmarchyMod never touches that file directly. See `SCOPE.md`.

[0.1.0]: https://github.com/JohnAndante/omarchymod/releases/tag/v0.1.0
