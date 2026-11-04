# Tasks: Native Recurrence and Persistent Alerts

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~500–700 additions + deletions |
| 400-line budget risk | High |
| Chained PRs recommended | No |
| Suggested split | 8 sequential test-first slices in the same working tree; no commits or PRs |
| Delivery strategy | exception-ok |
| Chain strategy | size-exception — explicitly approved single-working-tree sequence; no commits or PRs |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: High

## Scope and verification boundaries

- Implement only the approved `proposal.md`, `specs/`, and `design.md`. This checklist does not authorize edits to those artifacts.
- Keep production additions minimal: helper recurrence CRUD/export/stop and refresh state; one pure Python alert module; recurrence fields, confirmed stop, and critical notification dispatch in QML; bar counts; i18n/docs; CI provisioning if required.
- Use only the approved test seams: isolated helper CLI tests in `tests/test_recurrence_cli.py`, pure alert-state tests in `tests/test_alert_state.py`, and `tests/i18n.test.js` plus `./scripts/check`/qmllint. `scripts/check` already discovers `test_*.py`; do not add test-wiring coverage or new UI/argv/bar abstraction tests.
- Due alerts apply only to normalized `pending` tasks; `waiting` tasks and recurring templates are excluded. Templates may appear in all-status views but must not offer done/start actions; occurrences remain ordinary actionable task rows.
- Baseline is silent. Only later children of an already-known series can create occurrence alerts. Deduplicate across restarts, combine simultaneous reasons per task, and do not retry unchanged events. Tests must not invoke the live notifier, restart the shell, modify system configuration, or touch live Taskwarrior data.
- Run the slices below in order, in the same working tree. Each starts with a failing approved-seam test, adds only the minimum implementation, verifies, and can be reverted without changing Taskwarrior user data. The forecast is an explicit size exception, not a PR-chain recommendation.

## Ordered TDD slices

- [x] 1. **Establish an isolated CLI fixture and pinned CI runtime** — `tests/test_recurrence_cli.py`, `scripts/install-taskwarrior-ci` (new), `.github/workflows/check.yml`
   - **RED:** Add the helper CLI fixture using a temporary `HOME`, `TASKRC`, and `TASKDATA`; assert the fixture uses Taskwarrior 3.5.0 and confines Taskwarrior reads/writes to its temporary data.
   - **GREEN:** Provision Taskwarrior 3.5.0 in CI from its official source archive, verify SHA-256 `9ea64b411f8314414f440ec765dfdf5a86c9f6159df47e2f60cff3db6b31157a` before building, and fail on a wrong version. Do not rely on or guess an apt package version. Keep the existing Python unittest discovery in `scripts/check` unchanged.
   - **Verify:** Run the fixture against local 3.5.0, then confirm CI installs and checks the same version before `./scripts/check`.
   - **Rollback:** Remove only the installer/workflow changes and fixture setup; no persistent Taskwarrior data is involved.

- [x] 2. **Add recurrence-aware helper create and export** — `bin/omarchy-taskwarrior`, `tests/test_recurrence_cli.py`
  - [x] Assigned export normalization: distinguish recurring templates from occurrences and resolve each child interval from its active parent.
  - [x] Helper recurrence-create behavior and create-only assertions completed in the authorized follow-up slice.
   - **RED:** Test native recurring create/export in isolated data: template status/interval, pending child and `parentUuid`, distinct template/child identity, recurrence resolved onto the child, missing-due rejection before mutation (including `scheduled`-only), requested plugin UDA propagation, and start-timer targeting only the actionable child.
   - **GREEN:** Normalize recurrence, parent, and template identity in export; accept the native interval as one Taskwarrior argument; enforce due; re-export to identify template and child instead of assuming the first UUID is actionable.
   - **Verify:** Run the focused CLI cases on Taskwarrior 3.5.0 and compare helper output with native isolated exports.
   - **Rollback:** Revert helper normalization/create changes and their CLI cases; all test tasks live in temporary data.

- [x] 3. **Edit and stop series through the helper** — `bin/omarchy-taskwarrior`, `tests/test_recurrence_cli.py`
   - **RED:** Test enabling recurrence on a pending task, editing an occurrence so only its active parent template interval changes, rejecting `recur:` clearing, and stopping by template or child while retaining generated pending occurrences.
   - **GREEN:** Resolve UUIDs from native exports at mutation time; route recurrence edits to a verified active parent template, propagate requested UDAs after conversion, and implement `stop-series` by deleting only the validated template.
   - **Verify:** Run the isolated create/edit/stop cases and assert unrelated child fields and generated occurrences remain unchanged/pending.
   - **Rollback:** Revert the helper mutation paths and corresponding CLI cases; no live Taskwarrior records are touched.

- [x] 4. **Implement due eligibility and silent baseline** — `bin/alert_state.py` (new, pure), `tests/test_alert_state.py` (new)
   - **RED:** Test injected-time boundaries (past, now, exactly +24 hours, beyond +24 hours), pending-only eligibility, waiting/template exclusion, and a silent first baseline whose summary still counts existing eligible tasks.
   - **GREEN:** Implement deterministic due classification and baseline transitions without clock, filesystem, Taskwarrior, or notification I/O.
   - **Verify:** Run the focused unittest module and assert first-baseline notification records are empty while summary counts are correct.
   - **Rollback:** Remove the pure module and its tests; no integration or persistent state is involved.

- [x] 5. **Detect later children, aggregate reasons, and deduplicate** — `bin/alert_state.py`, `tests/test_alert_state.py`
   - **RED:** Test suppression of initial series children, detection of one or multiple later children under an existing template, no event from completion alone, combined due/occurrence reasons, unchanged-event replay/restart deduplication, and new events only after relevant identity/due/status changes. Verify pending-only new-occurrence summary pruning.
   - **GREEN:** Track known series/children and due fingerprints; return bounded next state, exact summaries, and one notification record per task with combined reasons.
   - **Verify:** Run pure deterministic transitions, including replay with returned prior state, and assert no second record for unchanged events.
   - **Rollback:** Revert this transition logic and its tests independently of helper/QML integration.

- [x] 6. **Persist alert state on successful helper refresh** — `bin/omarchy-taskwarrior`, `tests/test_recurrence_cli.py`
   - **RED:** Add isolated helper refresh cases for first-refresh silence, summary visibility, dedup across helper processes, `0700` directory/`0600` file, corrupt/unknown-state silent rebaseline, state-I/O failure emitting no records, and failed/unavailable exports not advancing state. Assert responses plan records but never launch a notifier.
   - **GREEN:** Add `refresh` over a successful normalized snapshot; atomically store versioned alert state at `~/.local/share/omarchy-taskwarrior/alert-state.json`, commit dedup state before returning records, fail closed on unsafe state I/O, and leave ordinary export/mutation responses non-notifying.
   - **Verify:** Run repeated helper processes under temporary `HOME`/`TASKRC`/`TASKDATA`; inspect permissions and confirm failed exports preserve prior state.
   - **Rollback:** Revert refresh/state persistence and the helper cases; remove only plugin-owned state under the temporary test HOME, never Taskwarrior data.

- [x] 7. **Wire recurrence controls and template-safe task rows** — `Panel.qml`, `Model.js`, `i18n.js`, `tests/i18n.test.js`
   - **RED:** Extend the existing i18n tests for English/Spanish recurrence label/help, due-required and stop guidance, and recurring-template status.
   - **GREEN:** Add create/edit recurrence fields and due validation before `runCmd`; block clearing an active interval in favor of confirmed stop-series; preserve recurrence/parent/template fields through `Model.js` snapshots; show templates distinctly in all-status views without done/start actions. Keep generated occurrences ordinary task rows.
   - **Verify:** Run `node --test tests/i18n.test.js` and `qmllint`; inspect that invalid submissions do not invoke the helper and ordinary delete remains separate from stop-series.
   - **Rollback:** Revert the recurrence UI/model/localization changes and assertions; no test starts the shell or changes system configuration.

- [x] 8. **Dispatch alerts, show bar counts, and document the feature** — `Panel.qml`, `BarWidget.qml`, `i18n.js`, `tests/i18n.test.js`, `README.md`, `CHANGELOG.md`, `.github/workflows/check.yml`
   - **RED:** Extend existing i18n assertions for notification title/reasons and overdue/upcoming/new-occurrence bar counts in English and Spanish.
   - **GREEN:** Route polling through helper `refresh`; queue records until settings/language are ready and serialize argv dispatch through `Quickshell.env("OMARCHY_PATH")/bin/omarchy-notification-send` with critical/persistent behavior, no shell interpolation, and no retry for unchanged records. Add `alertSummary` counts to the existing bar tooltip while retaining timer/pending/waiting lines and the pending pill. Document recurrence, manual dismissal/persistent alerts, and the Taskwarrior 3.5.0 check prerequisite; add an Unreleased changelog entry. Do not add a test command builder or summary module.
   - **Verify:** Run the i18n tests, `qmllint`, and `./scripts/check` with the Omarchy import path available. Confirm CI pins and verifies the source archive checksum and tests remain isolated from notification dispatch.
   - **Rollback:** Revert this UI/bar/docs/workflow integration slice; already-displayed desktop notifications cannot be recalled, so verification must never dispatch one.
