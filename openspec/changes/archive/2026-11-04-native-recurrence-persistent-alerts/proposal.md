# Proposal: Native Recurrence and Persistent Alerts

## Why

The plugin is a UI companion to Taskwarrior, but its create/edit forms and normalized export currently omit native recurrence. It also has no desktop alerts, leaving users to discover overdue, imminently due, and newly generated recurring tasks by reopening the panel or using the CLI. This change brings those workflows into the plugin without introducing a second task store or changing Taskwarrior as the source of truth.

## What Changes

- Add a recurrence field to task creation and editing that accepts free native Taskwarrior intervals (for example, `2w` or `3d`). Adding an interval to an ordinary pending task converts its UUID into a recurring template and creates a child occurrence; editing an existing occurrence updates its recurring template. Creating recurrence requires a due date; validate this in the UI because Taskwarrior rejects recurrence without one, even if `scheduled` is set. Add a stop-series action that deletes the template; already-generated occurrences remain pending. Preserve recurrence data in helper export and distinguish templates from occurrences. Use Taskwarrior’s native recurrence support; do not add a plugin-specific schedule engine.
- Notify for pending overdue tasks, pending tasks due within the next 24 hours, and new recurring occurrences generated after a series is created. Taskwarrior 3.5 may materialize occurrences as dates advance; detection must not assume completion directly creates the next occurrence. Do not notify for initial occurrences created with a series, or for eligible tasks present at first baseline. Send through Omarchy’s `omarchy-notification-send` helper with critical/persistent behavior; the user dismisses notifications manually. Persist deduplication across restarts. A defined task/event may notify only once, with no automatic resend after dismissal; a new notification is allowed only when event identity or relevant due/status data changes. Combine simultaneous reasons for the same task into one notification.
- Surface alert-relevant status in the bar using the existing overdue/actionable summary pattern. Add English and Spanish UI text.
- Add isolated Taskwarrior-helper CLI tests, pure alert-state logic tests, and include them in the repo check workflow.

## Capabilities

- **New:** native task recurrence management.
- **New:** persistent desktop alerts and visible bar status for urgent tasks and generated recurring occurrences.

## Scope Boundaries

Advanced recurrence masks and end rules are excluded. No changes to Taskwarrior’s task model, Timewarrior behavior, unrelated task fields, Omarchy system configuration, or shell restart behavior are part of this proposal. Validation must not send real desktop notifications or modify active system configuration.

## Impact

Expected areas: `bin/omarchy-taskwarrior` add/modify/export and task normalization; `Panel.qml` create/edit forms; `Model.js` task data; `BarWidget.qml` status/tooltip; a pure alert-state module; `i18n.js`; and tests plus `scripts/check`.

The helper currently omits recurrence from normalized task data. In the verified Taskwarrior 3.5.0 export example, a recurring template has `status=recurring` and its pending child has a `parent` reference to the template. The proposal does not infer broader recurrence lifecycle behavior from that observation.

## Acceptance Criteria

1. Create and edit forms expose native free-interval recurrence in English and Spanish. Creating recurrence without a due date is rejected with localized guidance. Adding recurrence to an ordinary pending task converts it into a series and exposes its generated child occurrence. Editing an occurrence changes its parent template interval. Stopping a series deletes its template while leaving generated occurrences pending. Taskwarrior remains responsible for interpreting and persisting the interval; recurrence is represented in the UI/export without conflating templates and occurrences.
2. Pending overdue and next-24-hour due eligibility is evaluated from due timestamps. A new recurring occurrence is recognized only when a child instance appears after the initial series creation; completing an occurrence is not assumed to generate it. Non-pending templates do not generate overdue/due alerts.
3. Notifications use Omarchy critical/persistent behavior and remain until manually dismissed. Initial baseline does not notify existing eligible tasks. Deduplication survives restarts; unchanged task data does not resend an alert. Due/recurrence reasons for one task are combined. Bar status visibly reflects the relevant alert state.
4. Tests exercise recurrence create/edit/stop/export through the helper CLI with isolated temporary Taskwarrior data, pure alert-state transitions/deduplication, and English/Spanish strings. `./scripts/check` passes. Tests do not emit real notifications, restart the shell, or change active system configuration.
5. Isolated Taskwarrior 3.5.0 experiments verify template/occurrence relationships, template interval editing, stop-series deletion behavior, and that clearing `recur` is rejected. The UI follows these native semantics.

## Risks and Rollback

- **Recurrence lifecycle ambiguity:** editing or deleting a template versus a child may have different native effects. Verify create, edit, completion/generation, and delete behavior against isolated temporary data; resolve the intended UI behavior before implementation rather than mutating live data speculatively.
- **Alert duplication or missed alerts:** startup reconciliation, restart deduplication, and overlapping due/recurrence events need product decisions below. Keep alert-state logic pure and test identity, transitions, and unchanged refreshes.
- **Rollback:** reverting the plugin change removes the UI, bar, and notification integration. Do not migrate or rewrite Taskwarrior data. Any plugin-owned alert bookkeeping is non-authoritative and removable; already-displayed desktop notifications cannot be retracted.

## Confirmed Decisions

- On first baseline, do not notify for existing eligible tasks; keep them visible in bar state.
- Persist notification deduplication across plugin/shell restarts.
- Notify for later Taskwarrior-generated child occurrences of an existing series, not the initial occurrence(s) created with the series. Detect the new child in exports; do not assume `done` immediately creates one.
- Edit recurrence interval on the parent template. Stop a series by deleting its template; already-generated occurrences remain pending.
- Combine simultaneous due/recurrence reasons for the same task into one persistent notification.
- Local Taskwarrior 3.5.0 experiments showed recurrence requires a due date, `recur:` cannot be cleared on a recurring template, and deleting its template stops future generation while keeping existing child tasks; do not clear `recur` to stop a series.
