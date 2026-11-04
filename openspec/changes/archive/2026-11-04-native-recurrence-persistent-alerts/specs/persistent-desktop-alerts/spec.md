# Persistent Desktop Alerts Specification

## Purpose

Make urgent pending tasks and newly generated recurring occurrences visible through persistent desktop notifications and the task bar status.

## Requirements

### Requirement: Alert on pending overdue and near-due tasks

The system MUST consider pending tasks overdue when their due timestamps are past and near-due when they fall within the next 24 hours. Non-pending recurring templates MUST NOT qualify for overdue or near-due alerts.

#### Scenario: Determine due alert eligibility

- GIVEN pending tasks with overdue timestamps or timestamps within the next 24 hours, alongside a non-pending recurring template
- WHEN alert eligibility is evaluated
- THEN the pending tasks qualify for their respective due reasons
- AND the recurring template does not qualify for an overdue or near-due reason

### Requirement: Detect recurring occurrences after initial creation

The system MUST recognize a new recurring-occurrence alert only when a child occurrence appears after the series' initial occurrence(s). Completing an occurrence alone MUST NOT be treated as evidence that another occurrence was generated.

#### Scenario: Detect a later generated child

- GIVEN a recurring series and the occurrence(s) created with that series
- WHEN an occurrence is completed but no additional child is present
- THEN no new-occurrence alert is eligible
- WHEN a later task export contains a previously unseen child of that series
- THEN that child is eligible for a new-occurrence alert

### Requirement: Suppress notifications at the first baseline

On the first alert baseline, the system MUST suppress notifications for eligible tasks that already exist, while keeping their alert-relevant status visible in the bar.

#### Scenario: Establish the first baseline

- GIVEN eligible pending tasks already exist when alert tracking first starts
- WHEN the first baseline is established
- THEN no notification is sent for those existing tasks
- AND their alert-relevant status remains visible in the bar

### Requirement: Persist notification deduplication

The system MUST persist notification deduplication across plugin and shell restarts. Unchanged task/event data MUST NOT cause an automatic resend, including after manual dismissal. A new notification MAY be sent only when the event identity or relevant due/status data changes.

#### Scenario: Restart with an unchanged dismissed event

- GIVEN a persistent notification for a task event was manually dismissed
- WHEN the plugin or shell restarts and the task/event data is unchanged
- THEN the system does not send that notification again

### Requirement: Combine simultaneous reasons for one task

When a task qualifies for multiple alert reasons at the same time, the system MUST combine those reasons into one notification for that task.

#### Scenario: One task has due and occurrence reasons

- GIVEN one task qualifies simultaneously for a due reason and a new recurring-occurrence reason
- WHEN notifications are produced
- THEN one notification for that task includes both reasons

### Requirement: Send persistent critical Omarchy notifications

Eligible alerts MUST be sent through Omarchy's `omarchy-notification-send` helper with critical, persistent behavior. A notification MUST remain until the user dismisses it manually and MUST NOT be resent automatically after dismissal for unchanged event data.

#### Scenario: Keep an alert until manual dismissal

- GIVEN an eligible task event produces a notification
- WHEN the notification is displayed
- THEN it uses critical persistent behavior and remains until the user dismisses it
- AND dismissal does not cause an automatic resend for unchanged event data

### Requirement: Surface alert-relevant status in the bar

The bar MUST visibly surface pending overdue tasks, tasks due within the next 24 hours, and newly generated recurring occurrences using the existing overdue/actionable summary pattern.

#### Scenario: Show alert-relevant task status

- GIVEN alert-relevant pending tasks or newly generated occurrences exist
- WHEN the bar status is displayed
- THEN the relevant alert state is visible in the existing summary pattern

### Requirement: Localize alert and status text

Alert-reason and bar-status UI text MUST be available in English and Spanish, and automated checks in `./scripts/check` MUST verify both languages.

#### Scenario: Display alert text in either supported language

- GIVEN English or Spanish is selected
- WHEN an alert reason or alert-relevant bar status is shown
- THEN its text is presented in the selected language
- AND automated checks verify the English and Spanish text

### Requirement: Verify alert state in isolation

Pure alert-state tests MUST cover due eligibility, first-baseline suppression, post-initial occurrence detection, combined reasons, and deduplication across restarts. They MUST run in `./scripts/check` without sending real desktop notifications, restarting the shell, or modifying active system configuration.

#### Scenario: Run isolated alert checks

- GIVEN `./scripts/check` runs the alert-state tests
- WHEN the tests exercise alert transitions and persisted deduplication
- THEN they verify the required alert state without invoking real notifications or changing active system configuration
