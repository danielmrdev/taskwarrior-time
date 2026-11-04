import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
HELPER = ROOT / "bin" / "omarchy-taskwarrior"
TASK = shutil.which("task")
REQUIRED_TASK_VERSION = "3.5.0"


class RecurrenceCliTest(unittest.TestCase):
    def setUp(self):
        if TASK is None:
            self.fail("Taskwarrior is required for recurrence CLI tests")

        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.taskdata = self.root / "taskdata"
        self.bin_dir = self.root / "bin"
        self.home.mkdir()
        self.taskdata.mkdir()
        self.bin_dir.mkdir()
        task_wrapper = self.bin_dir / "task"
        task_wrapper.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, subprocess, sys\n"
            "with open(os.environ['TASK_TEST_CALL_LOG'], 'a', encoding='utf-8') as log:\n"
            "    log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            "if os.path.exists(os.environ['TASK_TEST_FAIL_FILE']):\n"
            "    if os.path.exists(os.environ['TASK_TEST_FAIL_WITH_OUTPUT_FILE']) and 'export' in sys.argv[1:]:\n"
            "        result = subprocess.run([os.environ['TASK_TEST_REAL'], *sys.argv[1:]], capture_output=True, text=True)\n"
            "        sys.stdout.write(result.stdout)\n"
            "    sys.exit(1)\n"
            "os.execv(os.environ['TASK_TEST_REAL'], [os.environ['TASK_TEST_REAL'], *sys.argv[1:]])\n",
            encoding="utf-8",
        )
        task_wrapper.chmod(0o755)
        (self.bin_dir / "python3").symlink_to(sys.executable)

        self.task_call_log = self.root / "task-calls.jsonl"
        self.taskrc = self.root / "taskrc"
        self.taskrc.write_text(
            f"data.location={self.taskdata}\n"
            "confirmation=off\n"
            "verbose=nothing\n"
            "color=off\n"
            "uda.details.type=string\n"
            "uda.details.label=Details\n"
            "uda.waitingfor.type=string\n"
            "uda.waitingfor.label=Waiting for\n"
            "uda.outcome.type=string\n"
            "uda.outcome.label=Outcome\n",
            encoding="utf-8",
        )
        self.env = dict(os.environ)
        for name in ("TIMEWARRIORDB", "TIMEWARRIORDB_DIR", "TIMEWARRIORDB_FILE"):
            self.env.pop(name, None)
        self.env.update(
            HOME=str(self.home),
            TASKRC=str(self.taskrc),
            TASKDATA=str(self.taskdata),
            TASK_TEST_CALL_LOG=str(self.task_call_log),
            TASK_TEST_FAIL_FILE=str(self.root / "fail-task"),
            TASK_TEST_FAIL_WITH_OUTPUT_FILE=str(self.root / "fail-with-output"),
            TASK_TEST_REAL=TASK,
            # Keep helper subprocesses away from a user's Timewarrior binary.
            PATH=str(self.bin_dir),
        )

    def run_task(self, *args):
        return subprocess.run(
            [str(self.bin_dir / "task"), *args],
            check=False,
            capture_output=True,
            text=True,
            env=self.env,
        )

    def invoke_helper(self, *args):
        return subprocess.run(
            [str(HELPER), *args],
            check=False,
            capture_output=True,
            text=True,
            env=self.env,
        )

    def run_helper(self, *args):
        result = self.invoke_helper(*args)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        return json.loads(result.stdout)

    def task_calls(self):
        if not self.task_call_log.exists():
            return []
        return [
            json.loads(line)
            for line in self.task_call_log.read_text(encoding="utf-8").splitlines()
        ]

    def test_fixture_uses_taskwarrior_350_and_only_temporary_data(self):
        version = self.run_task("--version")
        self.assertEqual(version.returncode, 0, version.stderr or version.stdout)
        self.assertEqual(version.stdout.strip(), REQUIRED_TASK_VERSION)
        self.assertIsNone(shutil.which("timew", path=self.env["PATH"]))

        created = self.run_task("add", "--", "isolated fixture task")
        self.assertEqual(created.returncode, 0, created.stderr or created.stdout)

        data_location = self.run_task("_get", "rc.data.location")
        self.assertEqual(
            data_location.returncode,
            0,
            data_location.stderr or data_location.stdout,
        )
        self.assertEqual(Path(data_location.stdout.strip()).resolve(), self.taskdata.resolve())

        snapshot = self.run_helper("export")
        self.assertTrue(snapshot["ok"])
        self.assertEqual(
            [task["description"] for task in snapshot["tasks"]],
            ["isolated fixture task"],
        )
        self.assertTrue(any(self.taskdata.iterdir()))
        self.assertFalse((self.home / ".task").exists())
        self.assertFalse((self.home / ".taskrc").exists())

    def test_export_distinguishes_template_and_child_and_uses_parent_interval(self):
        created = self.run_task(
            "add", "due:tomorrow", "recur:2w", "--", "isolated recurring task"
        )
        self.assertEqual(created.returncode, 0, created.stderr or created.stdout)

        native_export = self.run_task("export")
        self.assertEqual(native_export.returncode, 0, native_export.stderr or native_export.stdout)
        native_tasks = json.loads(native_export.stdout)
        template = next(task for task in native_tasks if task.get("status") == "recurring")
        child = next(task for task in native_tasks if task.get("parent") == template["uuid"])
        self.assertEqual(template["recur"], "2w")
        self.assertEqual(child["status"], "pending")
        self.assertNotEqual(template["uuid"], child["uuid"])

        changed = self.run_task(template["uuid"], "modify", "recur:3w")
        self.assertEqual(changed.returncode, 0, changed.stderr or changed.stdout)
        native_after_edit_export = self.run_task("export")
        self.assertEqual(
            native_after_edit_export.returncode,
            0,
            native_after_edit_export.stderr or native_after_edit_export.stdout,
        )
        native_after_edit = json.loads(native_after_edit_export.stdout)
        native_template = next(
            task for task in native_after_edit if task.get("uuid") == template["uuid"]
        )
        native_child = next(
            task for task in native_after_edit if task.get("uuid") == child["uuid"]
        )
        self.assertEqual(native_template["recur"], "3w")
        self.assertEqual(native_child["recur"], "2w")

        snapshot = self.run_helper("export")
        self.assertTrue(snapshot["ok"])
        by_uuid = {task["uuid"]: task for task in snapshot["tasks"]}
        normalized_template = by_uuid[template["uuid"]]
        normalized_child = by_uuid[child["uuid"]]
        self.assertTrue(normalized_template["isRecurringTemplate"])
        self.assertEqual(normalized_template["recurrence"], "3w")
        self.assertEqual(normalized_template["parentUuid"], "")
        self.assertFalse(normalized_child["isRecurringTemplate"])
        self.assertEqual(normalized_child["parentUuid"], template["uuid"])
        self.assertEqual(normalized_child["recurrence"], "3w")
        self.assertNotEqual(normalized_template["uuid"], normalized_child["uuid"])

    def test_export_resolves_each_child_to_its_own_parent_interval(self):
        for description, interval in (
            ("first interval series", "2w"),
            ("second interval series", "5d"),
        ):
            created = self.run_task(
                "add", "due:tomorrow", f"recur:{interval}", "--", description
            )
            self.assertEqual(created.returncode, 0, created.stderr or created.stdout)

        native_export = self.run_task("export")
        self.assertEqual(native_export.returncode, 0, native_export.stderr or native_export.stdout)
        native_tasks = json.loads(native_export.stdout)
        templates = {
            task["description"]: task
            for task in native_tasks
            if task.get("status") == "recurring"
        }
        snapshot = self.run_helper("export")
        self.assertTrue(snapshot["ok"])
        by_uuid = {task["uuid"]: task for task in snapshot["tasks"]}

        for description, interval in (
            ("first interval series", "2w"),
            ("second interval series", "5d"),
        ):
            template = templates[description]
            child = next(
                task for task in native_tasks if task.get("parent") == template["uuid"]
            )
            self.assertEqual(by_uuid[template["uuid"]]["recurrence"], interval)
            self.assertEqual(by_uuid[child["uuid"]]["recurrence"], interval)
            self.assertEqual(by_uuid[child["uuid"]]["parentUuid"], template["uuid"])

    def test_ordinary_task_export_has_no_recurrence_identity(self):
        created = self.run_task("add", "--", "ordinary task")
        self.assertEqual(created.returncode, 0, created.stderr or created.stdout)

        snapshot = self.run_helper("export")
        self.assertEqual(len(snapshot["tasks"]), 1)
        task = snapshot["tasks"][0]
        self.assertFalse(task["isRecurringTemplate"])
        self.assertEqual(task["recurrence"], "")
        self.assertEqual(task["parentUuid"], "")

    def test_nonrecurring_helper_add_defaults_to_pending(self):
        response = self.run_helper(
            "add",
            "--description",
            "ordinary helper add",
            "--details",
            "ordinary task notes",
        )

        self.assertNotIn("templateUuid", response)
        self.assertEqual(len(response["tasks"]), 1)
        task = response["tasks"][0]
        self.assertEqual(response["createdUuid"], task["uuid"])
        self.assertEqual(task["description"], "ordinary helper add")
        self.assertEqual(task["status"], "pending")
        self.assertFalse(task["wait"])
        self.assertEqual(task["details"], "ordinary task notes")
        self.assertFalse(task["isRecurringTemplate"])
        self.assertEqual(task["recurrence"], "")

    def test_add_recurrence_returns_template_and_pending_child(self):
        response = self.run_helper(
            "add",
            "--description",
            "native recurring task",
            "--recur",
            "2w",
            "--due",
            "tomorrow",
        )

        native_export = self.run_task("export")
        self.assertEqual(
            native_export.returncode, 0, native_export.stderr or native_export.stdout
        )
        native_tasks = json.loads(native_export.stdout)
        templates = [task for task in native_tasks if task.get("status") == "recurring"]
        self.assertEqual(len(templates), 1)
        template = templates[0]
        children = [
            task for task in native_tasks if task.get("parent") == template["uuid"]
        ]
        self.assertEqual(len(children), 1)
        child = children[0]
        self.assertEqual(template["recur"], "2w")
        self.assertEqual(child["status"], "pending")
        self.assertFalse(child.get("wait"))
        self.assertNotEqual(template["uuid"], child["uuid"])
        self.assertEqual(response["templateUuid"], template["uuid"])
        self.assertEqual(response["createdUuid"], child["uuid"])

        normalized = {task["uuid"]: task for task in response["tasks"]}
        self.assertTrue(normalized[template["uuid"]]["isRecurringTemplate"])
        self.assertEqual(normalized[child["uuid"]]["parentUuid"], template["uuid"])
        self.assertEqual(normalized[child["uuid"]]["recurrence"], "2w")
        self.assertEqual(normalized[child["uuid"]]["status"], "pending")

    def test_add_recurrence_without_due_is_rejected_before_mutation(self):
        attempts = (
            ("recurrence without due", ()),
            ("scheduled only recurrence", ("--scheduled", "tomorrow")),
        )
        mutation_commands = {"add", "modify", "import", "done", "delete", "start"}

        for description, options in attempts:
            with self.subTest(description=description):
                before = self.run_task("export")
                self.assertEqual(before.returncode, 0, before.stderr or before.stdout)
                before_tasks = json.loads(before.stdout)
                call_offset = len(self.task_calls())

                result = self.invoke_helper(
                    "add",
                    "--description",
                    description,
                    "--recur",
                    "2w",
                    *options,
                )
                self.assertNotEqual(result.returncode, 0)
                payload = json.loads(result.stdout)
                self.assertIn("due", payload["error"].lower())

                after = self.run_task("export")
                self.assertEqual(after.returncode, 0, after.stderr or after.stdout)
                self.assertEqual(json.loads(after.stdout), before_tasks)
                attempted_calls = self.task_calls()[call_offset:]
                operations = [
                    next((arg for arg in call if not arg.startswith("rc.")), "")
                    for call in attempted_calls
                ]
                self.assertFalse(mutation_commands.intersection(operations), operations)

    def test_add_recurrence_propagates_plugin_fields_and_starts_only_child(self):
        dependency_add = self.run_task("add", "--", "recurrence dependency")
        self.assertEqual(
            dependency_add.returncode, 0, dependency_add.stderr or dependency_add.stdout
        )
        dependency = json.loads(self.run_task("export").stdout)[0]["uuid"]

        response = self.run_helper(
            "add",
            "--description",
            "recurrence with plugin fields",
            "--recur",
            "3d",
            "--due",
            "tomorrow",
            "--status",
            "pending",
            "--details",
            "keep these notes",
            "--waiting-for",
            "a reviewer",
            "--outcome",
            "approved",
            "--depend",
            dependency,
            "--start-timer",
        )

        native_export = self.run_task("export")
        self.assertEqual(
            native_export.returncode, 0, native_export.stderr or native_export.stdout
        )
        native_tasks = json.loads(native_export.stdout)
        template = next(task for task in native_tasks if task.get("status") == "recurring")
        children = [
            task for task in native_tasks if task.get("parent") == template["uuid"]
        ]
        self.assertEqual(len(children), 1)
        child = children[0]
        for generated in (template, *children):
            self.assertEqual(generated.get("details"), "keep these notes")
            self.assertEqual(generated.get("waitingfor"), "a reviewer")
            self.assertEqual(generated.get("outcome"), "approved")
            self.assertIn(dependency, generated.get("depends", []))
        self.assertEqual(response["templateUuid"], template["uuid"])
        self.assertEqual(response["createdUuid"], child["uuid"])
        self.assertFalse(template.get("start"))
        self.assertTrue(child.get("start"))

    @property
    def alert_state_path(self):
        return self.home / ".local" / "share" / "omarchy-taskwarrior" / "alert-state.json"

    def add_due_task(self, description="due refresh task", due="tomorrow"):
        result = self.run_task("add", f"due:{due}", "--", description)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        return json.loads(self.run_task("export").stdout)[-1]

    def add_native_series(self, interval="2w", description="series task"):
        added = self.run_task("add", "due:tomorrow", f"recur:{interval}", "--", description)
        self.assertEqual(added.returncode, 0, added.stderr or added.stdout)
        exported = self.run_task("export")
        self.assertEqual(exported.returncode, 0, exported.stderr or exported.stdout)
        tasks = json.loads(exported.stdout)
        template = next(task for task in tasks if task.get("status") == "recurring")
        child = next(task for task in tasks if task.get("parent") == template["uuid"])
        return template, child

    def test_modify_enables_recurrence_on_existing_pending_task(self):
        added = self.run_task("add", "--", "convert existing task")
        self.assertEqual(added.returncode, 0, added.stderr or added.stdout)
        original = json.loads(self.run_task("export").stdout)[0]

        response = self.run_helper(
            "modify", "--uuid", original["uuid"], "--recur", "3d",
            "--due", "tomorrow", "--details", "shared series notes",
        )
        native = json.loads(self.run_task("export").stdout)
        template = next(task for task in native if task["uuid"] == original["uuid"])
        self.assertEqual(template["status"], "recurring")
        self.assertEqual(template["recur"], "3d")
        child = next(task for task in native if task.get("parent") == template["uuid"])
        self.assertEqual(child["status"], "pending")
        self.assertEqual(template.get("details"), "shared series notes")
        self.assertEqual(child.get("details"), "shared series notes")
        normalized = {task["uuid"]: task for task in response["tasks"]}
        self.assertTrue(normalized[template["uuid"]]["isRecurringTemplate"])
        self.assertEqual(normalized[child["uuid"]]["parentUuid"], template["uuid"])
        self.assertEqual(normalized[child["uuid"]]["recurrence"], "3d")

    def test_modify_occurrence_routes_recurrence_only_to_active_parent(self):
        template, child = self.add_native_series()
        response = self.run_helper(
            "modify", "--uuid", child["uuid"], "--recur", "4w",
            "--description", "edited occurrence",
        )
        native = json.loads(self.run_task("export").stdout)
        by_uuid = {task["uuid"]: task for task in native}
        self.assertEqual(by_uuid[template["uuid"]]["recur"], "4w")
        self.assertEqual(by_uuid[child["uuid"]]["recur"], "2w")
        self.assertEqual(by_uuid[child["uuid"]]["description"], "edited occurrence")
        self.assertEqual(by_uuid[child["uuid"]]["parent"], template["uuid"])
        normalized = {task["uuid"]: task for task in response["tasks"]}
        self.assertEqual(normalized[child["uuid"]]["recurrence"], "4w")

    def test_recurrence_edit_requires_due_and_rejects_empty_interval_before_mutation(self):
        ordinary = self.run_task("add", "--", "no due task")
        self.assertEqual(ordinary.returncode, 0, ordinary.stderr or ordinary.stdout)
        task_uuid = json.loads(self.run_task("export").stdout)[0]["uuid"]
        before = json.loads(self.run_task("export").stdout)
        call_offset = len(self.task_calls())
        result = self.invoke_helper("modify", "--uuid", task_uuid, "--recur", "2w")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("due", json.loads(result.stdout)["error"].lower())
        self.assertEqual(json.loads(self.run_task("export").stdout), before)
        mutation_calls = self.task_calls()[call_offset:]
        operations = [next((arg for arg in call if not arg.startswith("rc.")), "") for call in mutation_calls]
        self.assertFalse({"modify", "import"}.intersection(operations), operations)

        template, _child = self.add_native_series()
        cleared = self.invoke_helper(
            "modify", "--uuid", template["uuid"], "--recur", ""
        )
        self.assertNotEqual(cleared.returncode, 0)
        self.assertIn("empty", json.loads(cleared.stdout)["error"].lower())
        after = json.loads(self.run_task("export").stdout)
        updated_template = next(task for task in after if task["uuid"] == template["uuid"])
        self.assertEqual(updated_template["recur"], "2w")

    def test_stop_series_from_template_or_occurrence_keeps_children_pending(self):
        for selected in ("template", "occurrence"):
            with self.subTest(selected=selected):
                template, child = self.add_native_series(description=f"series {selected}")
                selected_uuid = template["uuid"] if selected == "template" else child["uuid"]
                response = self.run_helper("stop-series", "--uuid", selected_uuid)
                native = json.loads(self.run_task("export").stdout)
                stopped_template = next(task for task in native if task["uuid"] == template["uuid"])
                self.assertEqual(stopped_template["status"], "deleted")
                self.assertNotIn(template["uuid"], {task["uuid"] for task in response["tasks"]})
                remaining_child = next(task for task in native if task["uuid"] == child["uuid"])
                self.assertEqual(remaining_child["status"], "pending")
                normalized = next(task for task in response["tasks"] if task["uuid"] == child["uuid"])
                self.assertEqual(normalized["recurrence"], "")
                self.assertEqual(normalized["parentUuid"], template["uuid"])
                self.assertFalse(normalized["isRecurringTemplate"])

    def test_stop_series_rejects_ordinary_task_without_deleting_it(self):
        added = self.run_task("add", "--", "not a series")
        self.assertEqual(added.returncode, 0, added.stderr or added.stdout)
        ordinary = json.loads(self.run_task("export").stdout)[0]
        result = self.invoke_helper("stop-series", "--uuid", ordinary["uuid"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("recurring", json.loads(result.stdout)["error"].lower())
        remaining = next(
            task for task in json.loads(self.run_task("export").stdout)
            if task["uuid"] == ordinary["uuid"]
        )
        self.assertEqual(remaining["status"], "pending")

    def test_orphaned_occurrence_recurrence_edit_fails_without_mutation(self):
        template, child = self.add_native_series()
        stopped = self.run_helper("stop-series", "--uuid", template["uuid"])
        orphan = next(task for task in stopped["tasks"] if task["uuid"] == child["uuid"])
        self.assertEqual(orphan["recurrence"], "")
        before = json.loads(self.run_task("export").stdout)
        before_by_uuid = {task["uuid"]: task for task in before}
        call_offset = len(self.task_calls())
        result = self.invoke_helper(
            "modify", "--uuid", child["uuid"], "--recur", "5d"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("parent", json.loads(result.stdout)["error"].lower())
        after_by_uuid = {task["uuid"]: task for task in json.loads(self.run_task("export").stdout)}
        self.assertEqual(after_by_uuid[child["uuid"]]["status"], before_by_uuid[child["uuid"]]["status"])
        self.assertEqual(after_by_uuid[child["uuid"]].get("recur"), before_by_uuid[child["uuid"]].get("recur"))
        mutation_calls = self.task_calls()[call_offset:]
        operations = [next((arg for arg in call if not arg.startswith("rc.")), "") for call in mutation_calls]
        self.assertFalse({"modify", "import"}.intersection(operations), operations)

    def test_add_recurrence_does_not_start_a_waiting_child(self):
        response = self.run_helper(
            "add",
            "--description",
            "waiting recurrence",
            "--recur",
            "2w",
            "--due",
            "tomorrow",
            "--status",
            "waiting",
            "--start-timer",
        )

        native_export = self.run_task("export")
        self.assertEqual(
            native_export.returncode, 0, native_export.stderr or native_export.stdout
        )
        native_tasks = json.loads(native_export.stdout)
        template = next(task for task in native_tasks if task.get("status") == "recurring")
        child = next(
            task for task in native_tasks if task.get("parent") == template["uuid"]
        )
        self.assertEqual(response["templateUuid"], template["uuid"])
        self.assertEqual(response["createdUuid"], child["uuid"])
        self.assertEqual(child["status"], "pending")
        self.assertTrue(child.get("wait"))
        self.assertFalse(template.get("start"))
        self.assertFalse(child.get("start"))

    def test_refresh_first_baseline_is_silent_but_reports_due_summary(self):
        self.add_due_task("upcoming refresh task", "tomorrow")
        self.add_due_task("overdue refresh task", "yesterday")
        result = self.run_helper("refresh")

        self.assertTrue(result["ok"])
        self.assertEqual(result["alertSummary"]["upcoming"], 1)
        self.assertEqual(result["alertSummary"]["overdue"], 1)
        self.assertEqual(result["notifications"], [])
        self.assertEqual(len(result["tasks"]), 2)
        self.assertTrue(self.alert_state_path.is_file())
        baseline_bytes = self.alert_state_path.read_bytes()
        exported = self.run_helper("export")
        self.assertNotIn("notifications", exported)
        self.assertEqual(self.alert_state_path.read_bytes(), baseline_bytes)

    def test_refresh_deduplicates_unchanged_event_across_processes_then_plans_change(self):
        task = self.add_due_task()
        first = self.run_helper("refresh")
        self.assertEqual(first["notifications"], [])

        changed = self.run_task(task["uuid"], "modify", "due:yesterday")
        self.assertEqual(changed.returncode, 0, changed.stderr or changed.stdout)
        second = self.run_helper("refresh")
        self.assertEqual([n["uuid"] for n in second["notifications"]], [task["uuid"]])
        third = self.run_helper("refresh")
        self.assertEqual(third["notifications"], [])
        self.assertEqual(second["alertSummary"]["overdue"], 1)
        self.assertFalse(any("notify" in " ".join(call).lower() for call in self.task_calls()))

    def test_refresh_alert_state_has_restrictive_permissions_and_bounded_json(self):
        self.add_due_task()
        self.run_helper("refresh")
        self.assertEqual(self.alert_state_path.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.alert_state_path.stat().st_mode & 0o777, 0o600)
        state = json.loads(self.alert_state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["version"], 1)
        self.assertTrue(state["initialized"])
        self.assertLess(self.alert_state_path.stat().st_size, 200_000)

    def test_refresh_corrupt_or_unknown_version_state_rebaselines_silently(self):
        self.add_due_task()
        for contents in ("{broken", json.dumps({"version": 999, "initialized": True})):
            with self.subTest(contents=contents):
                self.alert_state_path.parent.mkdir(parents=True, exist_ok=True)
                self.alert_state_path.write_text(contents, encoding="utf-8")
                refreshed = self.run_helper("refresh")
                self.assertEqual(refreshed["notifications"], [])
                self.assertTrue(json.loads(self.alert_state_path.read_text())["initialized"])

    def test_refresh_state_io_failure_fails_closed(self):
        self.add_due_task()
        state_directory = self.alert_state_path.parent
        state_directory.mkdir(parents=True)
        self.alert_state_path.mkdir()
        refreshed = self.run_helper("refresh")
        self.assertEqual(refreshed["notifications"], [])
        self.assertEqual(refreshed["alertSummary"]["upcoming"], 1)

    def test_nonzero_task_export_with_partial_json_does_not_advance_alert_state(self):
        task = self.add_due_task()
        self.run_helper("refresh")
        before = self.alert_state_path.read_bytes()
        changed = self.run_task(task["uuid"], "modify", "due:yesterday")
        self.assertEqual(changed.returncode, 0, changed.stderr or changed.stdout)
        Path(self.env["TASK_TEST_FAIL_FILE"]).touch()
        Path(self.env["TASK_TEST_FAIL_WITH_OUTPUT_FILE"]).touch()

        result = self.invoke_helper("refresh")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("error", json.loads(result.stdout))
        self.assertEqual(self.alert_state_path.read_bytes(), before)

    def test_failed_task_export_leaves_exact_alert_state_bytes_unchanged(self):
        self.add_due_task()
        self.run_helper("refresh")
        before = self.alert_state_path.read_bytes()
        Path(self.env["TASK_TEST_FAIL_FILE"]).touch()

        result = self.invoke_helper("refresh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("error", json.loads(result.stdout))
        self.assertEqual(self.alert_state_path.read_bytes(), before)

        Path(self.env["TASK_TEST_FAIL_FILE"]).unlink()
        task_command = self.bin_dir / "task"
        unavailable = self.bin_dir / "task.unavailable"
        task_command.rename(unavailable)
        try:
            missing = self.invoke_helper("refresh")
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("error", json.loads(missing.stdout))
            self.assertEqual(self.alert_state_path.read_bytes(), before)
        finally:
            unavailable.rename(task_command)


if __name__ == "__main__":
    unittest.main()
