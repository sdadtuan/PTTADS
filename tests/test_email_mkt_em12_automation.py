#!/usr/bin/env python3
"""Unit tests — EM-12 enterprise automation (journeys + experiments)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from ptt_email.experiments import assign_variant_key, resolve_subject_for_contact
from ptt_email.journey_engine import _next_step_by_label, enqueue_journey_cron_jobs
from ptt_email.triggers import process_pending_trigger_events


class ExperimentAssignmentTests(unittest.TestCase):
    def test_assign_variant_key_stable(self) -> None:
        variants = [
            {"variant_key": "control", "split_pct": 50},
            {"variant_key": "variant_a", "split_pct": 50},
        ]
        a = assign_variant_key(experiment_id="exp-1", contact_id="contact-1", variants=variants)
        b = assign_variant_key(experiment_id="exp-1", contact_id="contact-1", variants=variants)
        self.assertEqual(a, b)
        self.assertIn(a, {"control", "variant_a"})

    @patch("ptt_email.experiments.get_running_experiment_for_campaign")
    def test_resolve_subject_without_experiment(self, mock_get) -> None:
        mock_get.return_value = None
        subject, meta = resolve_subject_for_contact(
            campaign_id="cam-1",
            contact_id="c-1",
            default_subject="Hello",
        )
        self.assertEqual(subject, "Hello")
        self.assertEqual(meta, {})


class JourneyBranchGraphTests(unittest.TestCase):
    def test_next_step_by_label(self) -> None:
        graph = {
            "nodes": [
                {"id": "b1", "type": "branch"},
                {"id": "yes", "type": "send"},
                {"id": "no", "type": "exit"},
            ],
            "edges": [
                {"from": "b1", "to": "yes", "label": "yes"},
                {"from": "b1", "to": "no", "label": "no"},
            ],
        }
        self.assertEqual(_next_step_by_label(graph, "b1", "yes"), "yes")
        self.assertEqual(_next_step_by_label(graph, "b1", "no"), "no")

    @patch("ptt_jobs.enqueue.enqueue_job")
    def test_enqueue_journey_cron_includes_triggers(self, mock_enqueue) -> None:
        mock_enqueue.return_value = {"id": "j1"}
        out = enqueue_journey_cron_jobs()
        self.assertTrue(out["ok"])
        self.assertEqual(mock_enqueue.call_count, 3)
        job_types = [call.args[0] for call in mock_enqueue.call_args_list]
        self.assertIn("email_journey_trigger_events", job_types)


class TriggerProcessorTests(unittest.TestCase):
    @patch("ptt_email.triggers.email_journeys_enabled", return_value=False)
    def test_process_skipped_when_disabled(self, _mock_enabled) -> None:
        out = process_pending_trigger_events()
        self.assertTrue(out["ok"])
        self.assertTrue(out.get("skipped"))


if __name__ == "__main__":
    unittest.main()
