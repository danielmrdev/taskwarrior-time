# Native Task Recurrence Management Specification

## Purpose

Let users manage recurring task series through Taskwarrior's native recurrence behavior while keeping templates and generated occurrences distinguishable.

## Requirements

### Requirement: Create recurring tasks with native intervals

The system MUST let users create a recurring task using a free-form native Taskwarrior recurrence interval. Creating a recurring task MUST require a due date and provide localized guidance when one is missing, because Taskwarrior 3.5.0 rejects recurrence without `due:` even when `scheduled:` is present. Taskwarrior MUST remain authoritative for interpreting and storing the interval, and task views and helper exports MUST preserve recurrence data and distinguish a recurring template from its generated occurrences.

#### Scenario: Create and export a recurring task

- GIVEN a user enters a native interval such as `2w` and a due date when creating a task
- WHEN the task is created and exported
- THEN Taskwarrior represents the recurring template and its occurrence relationship
- AND the exported and displayed data preserves the interval and distinguishes the template from occurrences

#### Scenario: Reject recurrence without due date

- GIVEN a user enters a recurrence interval without a due date
- WHEN the user attempts to create the task
- THEN the plugin rejects the submission before invoking Taskwarrior
- AND shows localized guidance that recurring tasks need a due date

### Requirement: Edit a series recurrence interval

The system MUST let users edit a series' free-form recurrence interval. When the selected task is a generated occurrence, editing its recurrence MUST update the parent template's interval. Adding a recurrence interval to an ordinary pending task MUST follow Taskwarrior's native behavior: convert that UUID to a recurring template and expose its generated child occurrence.

#### Scenario: Enable recurrence on an existing task

- GIVEN an ordinary pending task with a due date
- WHEN the user adds a valid native recurrence interval and saves
- THEN Taskwarrior converts the task to a recurring template
- AND the helper export exposes the generated pending child occurrence

#### Scenario: Edit recurrence from a child occurrence

- GIVEN a generated occurrence with a parent recurring template
- WHEN the user edits the recurrence interval from that occurrence
- THEN the parent template has the new interval
- AND the task data continues to distinguish the template from the occurrence

### Requirement: Stop a recurring series

The system MUST provide an explicit stop-series operation that deletes the recurring template. Already-generated occurrences MUST remain pending after the template is deleted.

#### Scenario: Stop a series with generated occurrences

- GIVEN a recurring template with one or more generated pending occurrences
- WHEN the user stops the series
- THEN the template is deleted
- AND the generated occurrences remain pending

### Requirement: Localize recurrence controls

Recurrence creation, editing, and stop-series controls MUST have English and Spanish UI text, and automated checks in `./scripts/check` MUST verify both languages.

#### Scenario: Show recurrence controls in either supported language

- GIVEN the user selects English or Spanish
- WHEN the user opens task creation or editing, or the stop-series action
- THEN the recurrence controls and action text are presented in the selected language
- AND automated checks verify the English and Spanish text

### Requirement: Verify recurrence behavior with isolated helper tests

The recurrence helper CLI MUST be covered by tests using isolated temporary Taskwarrior data. The tests MUST verify create, edit-from-occurrence, stop-series, and export behavior against Taskwarrior 3.5.0 without modifying active Taskwarrior data, and MUST run in `./scripts/check`.

#### Scenario: Run recurrence checks safely

- GIVEN `./scripts/check` runs the recurrence tests
- WHEN the tests exercise the helper CLI
- THEN they use temporary Taskwarrior data and verify template/occurrence relationships, parent interval edits, template deletion, pending generated occurrences, and export distinctions
- AND they do not modify the user's active Taskwarrior data
