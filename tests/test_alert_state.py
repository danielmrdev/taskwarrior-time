import unittest
from datetime import datetime, timedelta, timezone

from bin.alert_state import reconcile


class AlertStateTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2025, 3, 8, 12, 0, tzinfo=timezone.utc)

    def task(self, uuid, *, status="pending", due="", wait="", template=False):
        return {
            "uuid": uuid,
            "status": status,
            "due": due,
            "wait": wait,
            "isRecurringTemplate": template,
        }

    def iso(self, moment):
        return moment.isoformat(timespec="seconds").replace("+00:00", "Z")

    def test_due_boundaries_are_overdue_upcoming_or_excluded(self):
        tasks = [
            self.task("past", due=self.iso(self.now - timedelta(seconds=1))),
            self.task("now", due=self.iso(self.now)),
            self.task("limit", due=self.iso(self.now + timedelta(hours=24))),
            self.task("later", due=self.iso(self.now + timedelta(hours=24, seconds=1))),
        ]

        result = reconcile(tasks, None, self.now)

        self.assertEqual(result["summary"], {"overdue": 1, "upcoming": 2, "newRecurrences": 0})
        self.assertEqual(result["notifications"], [])

    def test_only_pending_non_template_tasks_are_due_eligible(self):
        tasks = [
            self.task("waiting", status="waiting", due=self.iso(self.now - timedelta(hours=1))),
            self.task("recurring", status="recurring", due=self.iso(self.now), template=True),
            self.task("marked-template", due=self.iso(self.now), template=True),
            self.task("completed", status="completed", due=self.iso(self.now)),
            self.task("future-wait", due=self.iso(self.now), wait=self.iso(self.now + timedelta(seconds=1))),
            self.task("pending", due=self.iso(self.now)),
        ]

        result = reconcile(tasks, None, self.now)

        self.assertEqual(result["summary"], {"overdue": 0, "upcoming": 1, "newRecurrences": 0})
        self.assertEqual(result["notifications"], [])
        self.assertEqual(set(result["state"]["dueEvents"]), {"pending"})

    def test_missing_or_unknown_state_silently_baselines_but_counts_tasks(self):
        tasks = [
            self.task("overdue", due=self.iso(self.now - timedelta(minutes=1))),
            self.task("upcoming", due=self.iso(self.now + timedelta(hours=1))),
        ]

        for prior_state in (None, {"version": 999, "initialized": True}):
            with self.subTest(prior_state=prior_state):
                result = reconcile(tasks, prior_state, self.now)
                self.assertEqual(result["notifications"], [])
                self.assertEqual(result["summary"], {"overdue": 1, "upcoming": 1, "newRecurrences": 0})
                self.assertTrue(result["state"]["initialized"])
                self.assertEqual(set(result["state"]["dueEvents"]), {"overdue", "upcoming"})

    def test_new_due_event_after_baseline_is_reported(self):
        task = self.task("task", due=self.iso(self.now))
        baseline = reconcile([task], None, self.now)

        later = reconcile([task], baseline["state"], self.now)

        self.assertEqual(later["notifications"], [])
        changed = self.task("task", due=self.iso(self.now + timedelta(hours=1)))
        changed_result = reconcile([changed], baseline["state"], self.now)
        self.assertEqual(changed_result["notifications"], [{"uuid": "task", "reasons": ["upcoming"]}])

    def recurring_task(self, uuid, *, status="pending", parent=None, due="", wait="", template=False):
        task = self.task(uuid, status=status, due=due, wait=wait, template=template)
        task.update({"parentUuid": parent, "recurrence": "1d" if template else ""})
        return task

    def test_first_baseline_seeds_template_and_children_silently(self):
        tasks = [
            self.recurring_task("series", status="recurring", template=True),
            self.recurring_task("child-1", parent="series"),
            self.recurring_task("child-2", parent="series"),
        ]

        result = reconcile(tasks, None, self.now)

        self.assertEqual(result["notifications"], [])
        self.assertEqual(result["summary"]["newRecurrences"], 0)
        self.assertEqual(result["state"]["knownSeries"], {"series": ["child-1", "child-2"]})
        self.assertEqual(result["state"]["newOccurrences"], {})

    def test_first_seen_series_children_are_silent_but_later_child_alerts(self):
        original = [self.recurring_task("series", status="recurring", template=True),
                    self.recurring_task("first", parent="series")]
        baseline = reconcile(original, None, self.now)
        unseen_series = [self.recurring_task("series", status="recurring", template=True),
                         self.recurring_task("first", parent="series"),
                         self.recurring_task("new-series", status="recurring", template=True),
                         self.recurring_task("initial-a", parent="new-series"),
                         self.recurring_task("initial-b", parent="new-series")]

        seeded = reconcile(unseen_series, baseline["state"], self.now)
        later = reconcile(unseen_series + [
            self.recurring_task("later-a", parent="series"),
            self.recurring_task("later-b", parent="series"),
        ], seeded["state"], self.now)

        self.assertEqual(seeded["notifications"], [])
        self.assertEqual(seeded["state"]["knownSeries"]["new-series"], ["initial-a", "initial-b"])
        self.assertEqual(later["notifications"], [
            {"uuid": "later-a", "reasons": ["newRecurrence"]},
            {"uuid": "later-b", "reasons": ["newRecurrence"]},
        ])
        self.assertEqual(later["summary"]["newRecurrences"], 2)

    def test_completion_alone_is_not_occurrence_and_prunes_summary(self):
        tasks = [self.recurring_task("series", status="recurring", template=True),
                 self.recurring_task("child", parent="series")]
        baseline = reconcile(tasks, None, self.now)
        later = reconcile([tasks[0], self.recurring_task("child", parent="series", status="completed")], baseline["state"], self.now)

        self.assertEqual(later["notifications"], [])
        self.assertEqual(later["summary"]["newRecurrences"], 0)
        self.assertEqual(later["state"]["newOccurrences"], {})

    def test_new_occurrence_summary_prunes_completed_absent_and_future_wait_children(self):
        original = [self.recurring_task("series", status="recurring", template=True),
                    self.recurring_task("initial", parent="series")]
        baseline = reconcile(original, None, self.now)
        fresh = self.recurring_task("fresh", parent="series")
        waiting = self.recurring_task("waiting", parent="series", wait=self.iso(self.now + timedelta(hours=1)))
        detected = reconcile(original + [fresh, waiting], baseline["state"], self.now)

        self.assertEqual(detected["summary"]["newRecurrences"], 1)
        self.assertEqual(detected["notifications"], [{"uuid": "fresh", "reasons": ["newRecurrence"]}])
        pruned = reconcile(original + [fresh, self.recurring_task("waiting", parent="series", status="completed")], detected["state"], self.now)
        self.assertEqual(pruned["summary"]["newRecurrences"], 1)
        self.assertEqual(pruned["state"]["newOccurrences"], {"fresh": "series"})
        absent = reconcile(original, pruned["state"], self.now)
        self.assertEqual(absent["summary"]["newRecurrences"], 0)

    def test_new_occurrence_summary_survives_template_stop_while_pending(self):
        template = self.recurring_task("series", status="recurring", template=True)
        original = self.recurring_task("initial", parent="series")
        baseline = reconcile([template, original], None, self.now)
        fresh = self.recurring_task("fresh", parent="series")
        detected = reconcile([template, original, fresh], baseline["state"], self.now)

        stopped = reconcile([fresh], detected["state"], self.now)

        self.assertEqual(stopped["notifications"], [])
        self.assertEqual(stopped["summary"]["newRecurrences"], 1)
        self.assertEqual(stopped["state"]["newOccurrences"], {"fresh": "series"})

    def test_due_and_occurrence_reasons_are_merged_and_replay_is_deduplicated(self):
        template = self.recurring_task("series", status="recurring", template=True)
        existing = self.recurring_task("old", parent="series")
        baseline = reconcile([template, existing], None, self.now)
        fresh = self.recurring_task("fresh", parent="series", due=self.iso(self.now))

        notified = reconcile([template, existing, fresh], baseline["state"], self.now)
        replay = reconcile([template, existing, fresh], notified["state"], self.now)

        self.assertEqual(notified["notifications"], [{"uuid": "fresh", "reasons": ["upcoming", "newRecurrence"]}])
        self.assertEqual(replay["notifications"], [])
        self.assertEqual(replay["summary"]["newRecurrences"], 1)

    def test_due_status_change_can_realert_but_seen_occurrence_never_does(self):
        template = self.recurring_task("series", status="recurring", template=True)
        occurrence = self.recurring_task("fresh", parent="series", due=self.iso(self.now))
        baseline = reconcile([template], None, self.now)
        detected = reconcile([template, occurrence], baseline["state"], self.now)
        completed_then_pending = reconcile([template, self.recurring_task(
            "fresh", parent="series", status="pending", due=self.iso(self.now + timedelta(hours=1))
        )], detected["state"], self.now)

        self.assertEqual(detected["notifications"], [{"uuid": "fresh", "reasons": ["upcoming", "newRecurrence"]}])
        self.assertEqual(completed_then_pending["notifications"], [{"uuid": "fresh", "reasons": ["upcoming"]}])
        self.assertEqual(completed_then_pending["summary"]["newRecurrences"], 1)


if __name__ == "__main__":
    unittest.main()
