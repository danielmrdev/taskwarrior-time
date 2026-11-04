# Technical Design: Native Recurrence and Persistent Alerts

## Approach

Keep Taskwarrior authoritative for recurrence and task data. The Python helper owns export normalization, alert reconciliation, and persisted alert state; `Panel.qml` is the UI adapter for recurrence actions and notification dispatch. Alert decisions live in a pure Python module so first-baseline, recurrence-detection, due-window, aggregation, and dedup transitions can be tested without Quickshell or desktop services.

## Data flow and contracts

### Refresh and alert state

`BarWidget`'s existing startup/30-second refresh calls `Panel.refresh()`, which invokes a new helper `refresh` command. The helper obtains one successful Taskwarrior snapshot, normalizes it, loads/reconciles alert state, atomically persists the result, then returns the ordinary snapshot plus `alertSummary` and a `notifications` array. Ordinary `export` and mutation responses remain non-notifying; their snapshots can include a stateless/current `alertSummary`. This keeps notification dispatch tied to successful polling and avoids treating `done` as a recurrence hook. A later child is detected whenever a successful refresh export first contains its UUID.

The pure alert-state interface accepts normalized tasks, prior state, and an injected `now`, and returns next state, summary counts, and notification records. It does no filesystem, Taskwarrior, clock, or notification I/O. Records contain a task UUID and reason keys; the UI provides localized text.

State is stored separately from the allowlisted `ui-settings.json`, at `~/.local/share/omarchy-taskwarrior/alert-state.json` (directory `0700`, file `0600`). Versioned state contains:

- `initialized`, distinguishing first baseline from subsequent observations;
- current recurring template UUIDs and the child UUIDs currently present for each template;
- the current due-event fingerprint per eligible task (reason, pending status, exact due value);
- pending newly-generated occurrence UUIDs used by the bar summary.

This state is bounded by the helper's existing `MAX_TASKS` export ceiling: only current templates, exported children, currently eligible due events, and still-pending new occurrences are retained. On the first successful baseline, seed all current series/child relationships and due fingerprints but return no notifications. Thereafter, a first-seen template seeds its initial children without notifying; only additional child UUIDs under a previously known template create recurrence events. A changed due/status/reason fingerprint is a new due event; an unchanged fingerprint is not resent. When a due event ceases to be eligible, its current fingerprint is removed. New-occurrence bar state remains while that child is pending and is pruned when it is completed or absent.

Due eligibility uses normalized `status == pending` and UTC timestamps: past timestamps are overdue; timestamps from now through now + 24 hours are upcoming. Templates (`status == recurring`) and waiting/completed tasks are excluded. Counts are calculated independently of first-baseline suppression so existing eligible tasks remain visible in the bar.

The helper commits dedup state before returning planned notifications. `Panel.qml` queues returned records until settings have loaded (language selection is asynchronous), builds a translated title/body from the reason keys, and invokes `Quickshell.env("OMARCHY_PATH") + "/bin/omarchy-notification-send"` via an argv array with `-u critical`; it does not use a shell or hard-code the install path. Queue dispatch is serialized. A notification dispatch failure is logged and not automatically retried for the unchanged event, preserving at-most-once behavior. If `OMARCHY_PATH` is unavailable, dispatch fails safely; the helper has already committed state, so the event will not be resent. If state cannot be read/written safely, the helper emits no notifications; a corrupt/unknown state is re-baselined without a notification storm. Failed/unavailable task exports do not advance state. The bar still receives alert counts on successful snapshots.

### Recurrence model and mutations

The normalized task contract adds `recurrence` (native `recur` interval), `parentUuid`, and `isRecurringTemplate`. The template keeps Taskwarrior's `status=recurring` and its interval. Each child keeps its pending/completed status and parent UUID; export normalization resolves the parent's interval onto the child for display/editing. `Model.js`'s explicit `TASK_FIELDS` allowlist must carry these fields through snapshot replacement. Templates remain excluded from due alerts. They may appear in the all-status view with a localized recurring status and recurrence metadata, but must not expose done/start actions; generated occurrences remain ordinary task rows with recurrence/parent metadata. Editing or stopping from either row resolves the active template.

Create accepts a trimmed, free-form native interval and passes it as one argv value (`recur:<interval>`); the plugin does not parse or reinterpret interval grammar. Taskwarrior 3.5.0 requires `due` for recurrence, so both create and edit forms must validate that a recurrence interval has a due value and show a localized English/Spanish error before invoking the helper. The helper repeats this guard for direct CLI callers. `scheduled` alone is not sufficient. UI text clearing an existing series interval is not a stop operation: block save with localized guidance and use the explicit stop-series action; never send `recur:` to clear it.

After `task add` or an ordinary-task modification that enables recurrence, re-export and identify the template (`status=recurring`) and children by `parent`. Return the pending child as `createdUuid` (and the template UUID separately) rather than assuming the first new UUID is the actionable occurrence. Apply plugin-owned UDAs (`details`, `waitingfor`, `outcome`) to the template and the generated child/children when requested, so helper behavior that previously patched only the first UUID does not leave the visible occurrence without its data. Apply start-timer behavior only to the actionable child, not the template. Keep Taskwarrior-native interval, due, dependency, and child-generation semantics intact.

For recurrence edits, the helper re-exports and resolves the selected task UUID at mutation time. If it is an occurrence, it verifies that `parentUuid` resolves to an active recurring template and routes only `--recur` to that template; other task fields continue targeting the selected task. Editing the template itself targets its own UUID. Setting recurrence on an ordinary task is allowed: Taskwarrior converts that UUID to a recurring template and may create a child, so the helper re-exports and propagates requested UDAs to the template and new child. If the parent is missing or is not a recurring template, recurrence edits fail safely rather than modifying an arbitrary task.

`stop-series --uuid <template-or-occurrence>` resolves and validates the active template, then deletes only that template. It does not clear `recur:` and does not delete generated children. The UI exposes a localized, confirmed Stop series action for the template or its occurrence. The existing ordinary delete operation remains separate.

### Bar and localized text

The snapshot's `alertSummary` reports `overdue`, `upcoming`, and `newRecurrences`. `BarWidget.composeTooltip()` adds these counts using the existing concise summary pattern (retaining the existing pending/waiting/timer lines); current actionable counts are not used as a substitute for exact timestamp eligibility. English and Spanish strings cover recurrence controls, due-required/stop guidance, notification title/reasons, and tooltip counts. The pending count/pill behavior remains unchanged.

## File changes

- `bin/omarchy-taskwarrior`: preserve recurrence/parent data; add recurrence-aware add/modify and validated `stop-series`; share snapshot building between `export` and `refresh`; implement private atomic alert-state I/O and return summary/planned notification records.
- `bin/alert_state.py` (new): pure due eligibility, baseline, known-series child diff, reason aggregation, dedup, and summary logic.
- `Panel.qml`: recurrence draft/create/editor fields, due validation, parent-aware stop action, refresh invocation, localized notification queue/argv dispatch, and settings-readiness gate.
- `Model.js`: add the explicit recurrence fields to task copying and represent recurring template/occurrence rows distinctly.
- `BarWidget.qml`, `i18n.js`: show alert counts and add English/Spanish alert and recurrence strings.
- `tests/`: Python tests for pure alert-state transitions and isolated helper/Taskwarrior recurrence CLI behavior; extend `tests/i18n.test.js` for both languages.
- `scripts/check`, `.github/workflows/check.yml`: run these tests and provision/verify Taskwarrior **3.5.0**; do not rely on an unspecified Ubuntu package version.

## Verification

1. Pure alert-state tests inject deterministic timestamps and cover exact overdue/24-hour boundaries, non-pending/template exclusion, first-baseline suppression with visible counts, initial-child suppression, later child UUID detection (including multiple children appearing together), completion without a new UUID, combined reasons, unchanged refresh/restart dedup, and changed due/status fingerprints.
2. Helper CLI tests set a temporary `HOME`, `TASKRC`, and `TASKDATA` for each case and require Taskwarrior 3.5.0. Verify recurring add/export and parent mapping; missing-due rejection; conversion of an existing pending task to a template plus generated child; UDA propagation; interval edits from a child updating only its template; `recur:` clearing rejection; and stop-series deleting the template while generated occurrences remain pending. Tests invoke no notifier and do not touch the active Taskwarrior store.
3. Extend English/Spanish translation assertions. `./scripts/check` runs the Python and Node tests and existing QML lint/static validation. Tests must not invoke the live notification helper, restart the shell, or change active system configuration.

## Rollout and failure behavior

The first successful refresh after installation or loss of state writes a silent baseline; the bar immediately reflects current overdue/upcoming tasks. Later refreshes notify only newly observed event fingerprints. The state file is plugin bookkeeping only and can be removed without changing Taskwarrior data; removal causes a fresh silent baseline. A failed Taskwarrior export leaves state unchanged for the next poll. Notification delivery is at-most-once after state commit; a failed dispatcher may miss that individual notification, but the bar summary remains available and unchanged data is not resent. No Taskwarrior migration or shell restart is required.

There are no unresolved product decisions. A CI provisioning step for the pinned Taskwarrior 3.5.0 test dependency is an implementation prerequisite.