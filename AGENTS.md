# Project Context

Omarchy Taskwarrior is an Omarchy Quickshell bar plugin for Taskwarrior and optional Timewarrior.

- Plugin ID is `omarchy-taskwarrior`; keep the manifest, QML module/IPC IDs, marketplace links, and install docs aligned.
- `origin` points to this fork; no `upstream` remote is configured. Local branch is `main`.
- UI languages: English and Spanish. `system` selects from the current locale; update settings validation, translations, tests, and docs together when changing language support.
- Run `./scripts/check` for manifest validation, Node/Python tests, and QML lint. Requires Node.js, Python 3, Qt `qmllint`, and Omarchy shell imports; set `OMARCHY_PATH` if Omarchy is outside `/usr/share/omarchy`.
