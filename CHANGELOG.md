# Changelog

All notable changes to **Omarchy Taskwarrior** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- IPC action `newTask` opens the Tasks view and focuses the composer for configurable Hyprland keybindings
- Spanish UI with system-locale detection and manual selection in About

## [1.0.2] - 2026-09-29

### Fixed

- Data directory and plugin files (`debug.log`, `ui-settings.json`, `extra-projects.json`) are created/repaired as `0700` / `0600` so other local users cannot read task text from debug logs
- Debug `cmd.*` events no longer log free-text task descriptions (flags/UUIDs/verbs only)

### Screenshots

- Refreshed English About screenshot (`docs/screenshots/en/03-about.png`) for v1.0.2

## [1.0.1] - 2026-09-26

### Added

- About: **What's new**, **Report a problem**, **Open on GitHub**, and **Omarchy Marketplace** actions
- About: **Open log folder** and **Clear logs** for bug-report workflows
- Root `CHANGELOG.md` and marketplace listing link in README
- Debug sessions now write a human-readable banner plus an environment fingerprint (plugin, Taskwarrior, Timewarrior, Omarchy, OS/desktop/locale)

### Changed

- About tab redesigned with PanelHero, section headers, and bordered action buttons
- Debug log format upgraded to schema v1 NDJSON with `level` and `component`
- README documents how to capture and attach a full debug log

### Fixed

- “Waiting for” text could fail to appear in the editor

### Screenshots

- Refreshed English About screenshot (`docs/screenshots/en/03-about.png`)

## [1.0.0] - 2026-09-23

### Added

- First public release: Omarchy bar widget over Taskwarrior + Timewarrior
- Task list with grouping, filters, in-place editor, projects tab
- Timers, dependencies, schedule fields, English UI
- Marketplace listing and signed GitHub release assets

[1.0.2]: https://github.com/DataArchitectPro/taskwarrior-time/releases/tag/v1.0.2
[1.0.1]: https://github.com/DataArchitectPro/taskwarrior-time/releases/tag/v1.0.1
[1.0.0]: https://github.com/DataArchitectPro/taskwarrior-time/releases/tag/v1.0.0
