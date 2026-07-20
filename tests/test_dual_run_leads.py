
import os
import unittest

if os.environ.get("PTT_RUN_FLASK_TESTS") != "1":
    raise unittest.SkipTest(
        "Flask HTTP removed — set PTT_RUN_FLASK_TESTS=1 to run integration tests"
    )
from tests.leads_v1_contract import load_golden


class TestDualRunDiff(unittest.TestCase):
    def test_diff_lead_identical(self) -> None:
        golden = load_golden("lead_v1.json")
        self.assertEqual(diff_lead_v1(golden, dict(golden)), [])

    def test_diff_lead_mismatch(self) -> None:
        golden = load_golden("lead_v1.json")
        other = dict(golden)
        other["phone"] = "0999999999"
        diffs = diff_lead_v1(golden, other)
        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0].field, "phone")

    def test_diff_lead_timestamp_format_equivalent(self) -> None:
        a = {"id": 1, "created_at": "2026-06-23T11:16:04Z", "received_at": "2026-06-23T11:16:04Z"}
        b = {"id": 1, "created_at": "2026-06-23 11:16:04", "received_at": "2026-06-23 11:16:04"}
        self.assertEqual(diff_lead_v1(a, b), [])

    def test_diff_list_response_golden(self) -> None:
        golden = load_golden("list_leads_response.json")
        self.assertEqual(diff_list_response(golden, dict(golden)), [])


class TestDualRunFetch(unittest.TestCase):
    @patch("ptt_crm.dual_run.fetch_nest_json")
    def test_compare_lead_get_match(self, mock_fetch: MagicMock) -> None:
        golden = load_golden("lead_v1.json")
        mock_fetch.return_value = (200, golden, None)
        result = compare_lead_get(1, golden)
        self.assertTrue(result.matched)
        self.assertEqual(result.diffs, [])

    @patch("ptt_crm.dual_run.fetch_nest_json")
    def test_compare_lead_get_status_mismatch(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = (404, {"error": "Not found"}, None)
        golden = load_golden("lead_v1.json")
        result = compare_lead_get(1, golden)
        self.assertFalse(result.matched)
        self.assertEqual(result.diffs[0].field, "http_status")

    @patch("ptt_crm.dual_run.fetch_nest_json")
    def test_compare_leads_list_match(self, mock_fetch: MagicMock) -> None:
        golden = load_golden("list_leads_response.json")
        mock_fetch.return_value = (200, golden, None)
        result = compare_leads_list(golden, query="limit=50&offset=0")
        self.assertTrue(result.matched)

    @patch("ptt_crm.dual_run.report_dual_run_mismatch")
    def test_run_dual_run_check_reports_mismatch(self, mock_report: MagicMock) -> None:
        from ptt_crm.dual_run import DualRunResult, FieldDiff

        bad = DualRunResult(
            endpoint="test",
            matched=False,
            diffs=[FieldDiff(field="x", flask=1, nest=2)],
        )
        run_dual_run_check(bad)
        mock_report.assert_called_once()


class TestDualRunBatch(unittest.TestCase):
    @patch("ptt_crm.dual_run.compare_lead_get")
    @patch("ptt_crm.dual_run.compare_leads_list")
    @patch("ptt_crm.dual_run.sample_lead_ids", return_value=[1])
    @patch("ptt_crm.leads_read.get_lead_v1")
    @patch("ptt_crm.leads_read.list_leads_v1", return_value=([{"id": 1}], 1))
    def test_batch_ok(
        self,
        _list: MagicMock,
        mock_get: MagicMock,
        _ids: MagicMock,
        mock_list_cmp: MagicMock,
        mock_get_cmp: MagicMock,
    ) -> None:
        from ptt_crm.dual_run import DualRunResult

        golden = load_golden("lead_v1.json")
        mock_get.return_value = golden
        ok = DualRunResult(endpoint="e", matched=True)
        mock_list_cmp.return_value = ok
        mock_get_cmp.return_value = ok

        with patch("ptt_crm.dual_run.run_dual_run_check", side_effect=lambda r: r):
            report = run_batch_dual_run_check(sample_size=1)
        self.assertTrue(report["ok"])
        self.assertEqual(report["mismatch_count"], 0)


class TestDualRunBlueprint(unittest.TestCase):
    @patch("app._admin_logged_in", return_value=True)
    @patch("blueprints.crm_leads_v1._can", return_value=True)
    @patch("ptt_crm.dual_run.maybe_dual_run_list")
    @patch("ptt_crm.leads_read.list_leads_v1", return_value=([], 0))
    def test_list_triggers_dual_run(
        self,
        _read: MagicMock,
        mock_dual: MagicMock,
        _can: MagicMock,
        _auth: MagicMock,
    ) -> None:
        from app import app

        client = app.test_client()
        resp = client.get("/api/v1/leads?limit=5")
        self.assertEqual(resp.status_code, 200)
        mock_dual.assert_called_once()


if __name__ == "__main__":
    unittest.main()
