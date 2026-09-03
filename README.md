# OmarchyMod

Companion package that makes [hyprmod](https://github.com/BlueManCZ/hyprmod)
work properly inside [Omarchy](https://github.com/basecamp/omarchy).

hyprmod is a GTK4/libadwaita settings app for Hyprland with live preview and
editors for binds, monitors, bezier curves, window rules and profiles. On
Omarchy it needs a bit of wiring to persist across reloads and to match the
active theme. OmarchyMod adds that layer from the outside: it does not fork
hyprmod, it installs it as a dependency and configures it.

## Status

Early. Nothing is packaged or usable yet. See [SCOPE.md](SCOPE.md) for the
design and the open decisions.

## What it will do

- Detect an Omarchy install and point hyprmod's managed config file somewhere
  Hyprland's Lua loader actually reloads.
- Wire hyprmod's managed file into `~/.config/hypr/hyprland.lua` (delegating to
  hyprmod's own setup), with a backup and a clean uninstall.
- Sync the active theme's `gtk.css` into `~/.config/gtk-4.0` so libadwaita apps
  stop rendering as default Adwaita, and keep it in sync on theme changes via an
  Omarchy `theme-set` hook.

## License

GPL-3.0, matching hyprmod.
