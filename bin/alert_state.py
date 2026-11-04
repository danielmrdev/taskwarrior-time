"""Pure due-alert eligibility and recurring-occurrence reconciliation."""

from datetime import datetime, timedelta, timezone
from typing import Any


STATE_VERSION = 1
DUE_WINDOW = timedelta(hours=24)


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_now(now: datetime) -> datetime:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return now.astimezone(timezone.utc)


def _task_series(tasks: list[dict[str, Any]]) -> tuple[dict[str, set[str]], set[str]]:
    templates: set[str] = set()
    children: dict[str, set[str]] = {}
    for task in tasks:
        if not isinstance(task, dict):
            continue
        uuid = task.get("uuid")
        if not isinstance(uuid, str) or not uuid:
            continue
        if task.get("isRecurringTemplate") is True or task.get("status") == "recurring":
            templates.add(uuid)
        parent = task.get("parentUuid")
        if isinstance(parent, str) and parent:
            children.setdefault(parent, set()).add(uuid)
    return {template: children.get(template, set()) for template in templates}, templates


def reconcile(
    tasks: list[dict[str, Any]],
    prior_state: dict[str, Any] | None,
    now: datetime,
) -> dict[str, Any]:
    """Reconcile due and later-occurrence events without side effects.

    State is bounded to current templates/children, eligible due fingerprints,
    and pending newly generated occurrences. ``knownSeries`` maps current
    template UUIDs to the child UUIDs present in the latest snapshot. A valid
    initialized state is required for transition detection; otherwise the
    current snapshot is a silent baseline. ``newOccurrences`` maps currently
    pending, newly detected actionable child UUIDs to their parent template.
    """
    current_time = _normalize_now(now)
    valid_prior = (
        isinstance(prior_state, dict)
        and prior_state.get("version") == STATE_VERSION
        and prior_state.get("initialized") is True
        and isinstance(prior_state.get("dueEvents"), dict)
        and isinstance(prior_state.get("knownSeries"), dict)
        and isinstance(prior_state.get("newOccurrences"), dict)
    )
    baseline = not valid_prior
    previous_events = prior_state["dueEvents"] if valid_prior else {}
    previous_series = prior_state["knownSeries"] if valid_prior else {}
    previous_occurrences = prior_state["newOccurrences"] if valid_prior else {}
    series, _ = _task_series(tasks)

    due_events: dict[str, dict[str, str]] = {}
    reason_map: dict[str, list[str]] = {}
    overdue_count = 0
    upcoming_count = 0
    window_end = current_time + DUE_WINDOW
    eligible_pending: dict[str, str] = {}

    for task in tasks:
        if not isinstance(task, dict) or task.get("status") != "pending" or task.get("isRecurringTemplate") is True:
            continue
        uuid = task.get("uuid")
        if not isinstance(uuid, str) or not uuid:
            continue
        wait_time = _parse_timestamp(task.get("wait"))
        if wait_time is not None and wait_time > current_time:
            continue
        eligible_pending[uuid] = task.get("parentUuid") if isinstance(task.get("parentUuid"), str) else ""
        due_value = task.get("due")
        due_time = _parse_timestamp(due_value)
        if due_time is None:
            continue
        if due_time < current_time:
            reason = "overdue"
            overdue_count += 1
        elif due_time <= window_end:
            reason = "upcoming"
            upcoming_count += 1
        else:
            continue
        fingerprint = {"reason": reason, "status": "pending", "due": str(due_value)}
        due_events[uuid] = fingerprint
        if not baseline and previous_events.get(uuid) != fingerprint:
            reason_map.setdefault(uuid, []).append(reason)

    new_occurrences: dict[str, str] = {}
    for child, template in previous_occurrences.items():
        if child in eligible_pending and eligible_pending[child] == template:
            new_occurrences[child] = template
    for template, child_ids in series.items():
        prior_children = set(previous_series.get(template, [])) if valid_prior and isinstance(previous_series.get(template, []), list) else set()
        is_known_series = valid_prior and template in previous_series
        for child in sorted(child_ids):
            if is_known_series and child not in prior_children and child in eligible_pending:
                new_occurrences[child] = template
                if not baseline:
                    reason_map.setdefault(child, []).append("newRecurrence")

    # Merge reasons while preserving due-first and stable task order.
    notifications = [{"uuid": uuid, "reasons": reasons} for uuid, reasons in reason_map.items()]
    return {
        "state": {
            "version": STATE_VERSION,
            "initialized": True,
            "dueEvents": due_events,
            "knownSeries": {template: sorted(children) for template, children in sorted(series.items())},
            "newOccurrences": new_occurrences,
        },
        "summary": {
            "overdue": overdue_count,
            "upcoming": upcoming_count,
            "newRecurrences": len(new_occurrences),
        },
        "notifications": notifications,
    }
