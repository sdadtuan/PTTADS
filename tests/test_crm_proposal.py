from __future__ import annotations
import json
import sqlite3
import unittest
from unittest.mock import MagicMock, patch
import crm_proposal as m


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE crm_customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT '',
            company TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '',
            address TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE crm_leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL DEFAULT '',
            product_interest TEXT NOT NULL DEFAULT '',
            need TEXT NOT NULL DEFAULT '',
            converted_customer_id INTEGER
        );
        CREATE TABLE crm_contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            amount_vnd INTEGER NOT NULL DEFAULT 0,
            title TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'draft'
        );
        CREATE TABLE crm_service_lifecycle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            service_slug TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'draft',
            stage TEXT NOT NULL DEFAULT 'lead'
        );
    """)
    conn.execute("CREATE TABLE IF NOT EXISTS crm_staff (id INTEGER PRIMARY KEY)")
    from crm_svc_tasks import ensure_schema as tasks_schema

    tasks_schema(conn)
    m.ensure_schema(conn)
    return conn


def _seed_customer(conn: sqlite3.Connection, name: str = "Test KH", company: str = "Test Co") -> int:
    conn.execute("INSERT INTO crm_customers (name, company) VALUES (?, ?)", (name, company))
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


class TestEnsureSchema(unittest.TestCase):
    def test_table_created(self):
        conn = _setup_conn()
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        self.assertIn("crm_proposals", tables)

    def test_idempotent(self):
        conn = _setup_conn()
        m.ensure_schema(conn)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM crm_proposals").fetchone()[0], 0)


class TestCreateProposal(unittest.TestCase):
    def test_returns_int_id(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        pid = m.create_proposal(conn, cid, ["dich-vu-seo-local"], 5000000, 3, "")
        self.assertIsInstance(pid, int)
        self.assertGreater(pid, 0)

    def test_lifecycle_id_nullable(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        pid = m.create_proposal(conn, cid, ["dich-vu-aeo"], 1000000, 1, "", lifecycle_id=None)
        row = conn.execute("SELECT lifecycle_id FROM crm_proposals WHERE id = ?", (pid,)).fetchone()
        self.assertIsNone(row["lifecycle_id"])

    def test_service_slugs_stored_as_json(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        slugs = ["dich-vu-seo-local", "dich-vu-aeo"]
        pid = m.create_proposal(conn, cid, slugs, 5000000, 3, "")
        row = conn.execute("SELECT service_slugs FROM crm_proposals WHERE id = ?", (pid,)).fetchone()
        self.assertEqual(json.loads(row["service_slugs"]), slugs)


class TestListProposals(unittest.TestCase):
    def test_empty_returns_empty_list(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        self.assertEqual(m.list_proposals(conn, cid), [])

    def test_generated_flag_false_by_default(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        m.create_proposal(conn, cid, ["dich-vu-aeo"], 1000000, 1, "")
        rows = m.list_proposals(conn, cid)
        self.assertFalse(rows[0]["generated"])

    def test_generated_flag_true_when_ai_output_set(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        pid = m.create_proposal(conn, cid, ["dich-vu-aeo"], 1000000, 1, "")
        conn.execute(
            "UPDATE crm_proposals SET ai_output = ? WHERE id = ?",
            ('{"problem":"x","solution":"y","usp":"z","kpi":"k","pricing_narrative":"p"}', pid),
        )
        conn.commit()
        rows = m.list_proposals(conn, cid)
        self.assertTrue(rows[0]["generated"])


class TestGetProposal(unittest.TestCase):
    def test_returns_none_when_not_found(self):
        conn = _setup_conn()
        self.assertIsNone(m.get_proposal(conn, 999))

    def test_parses_service_slugs_and_ai_output(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        pid = m.create_proposal(conn, cid, ["dich-vu-seo-local"], 5000000, 3, "")
        p = m.get_proposal(conn, pid)
        self.assertIsNotNone(p)
        self.assertIsInstance(p["service_slugs"], list)
        self.assertIsInstance(p["ai_output"], dict)


class TestDeleteProposal(unittest.TestCase):
    def test_deletes_row(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        pid = m.create_proposal(conn, cid, ["dich-vu-aeo"], 1000000, 1, "")
        m.delete_proposal(conn, pid)
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM crm_proposals WHERE id = ?", (pid,)).fetchone()[0],
            0,
        )


class TestGetCustomerContext(unittest.TestCase):
    def test_no_lead_returns_none_lead(self):
        conn = _setup_conn()
        cid = _seed_customer(conn, "Test KH", "Test Co")
        ctx = m.get_customer_context(conn, cid)
        self.assertIsNone(ctx["lead"])
        self.assertEqual(ctx["customer"]["name"], "Test KH")

    def test_with_lead_pulls_product_interest(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        conn.execute(
            "INSERT INTO crm_leads (full_name, product_interest, need, converted_customer_id) VALUES (?,?,?,?)",
            ("Test KH", "SEO Local", "Tăng traffic", cid),
        )
        conn.commit()
        ctx = m.get_customer_context(conn, cid)
        self.assertIsNotNone(ctx["lead"])
        self.assertEqual(ctx["lead"]["product_interest"], "SEO Local")
        self.assertEqual(ctx["lead"]["need"], "Tăng traffic")

    def test_context_includes_consult_task(self):
        from crm_svc_tasks import seed_tasks, update_task

        conn = _setup_conn()
        cid = _seed_customer(conn)
        conn.execute(
            """
            INSERT INTO crm_service_lifecycle (customer_id, service_slug, stage, status)
            VALUES (?, 'dich-vu-seo-tong-the', 'consult', 'active')
            """,
            (cid,),
        )
        lid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        seed_tasks(conn, lifecycle_id=lid, service_slug="dich-vu-seo-tong-the")
        consult_id = conn.execute(
            "SELECT id FROM crm_svc_tasks WHERE lifecycle_id = ? AND stage = 'consult'",
            (lid,),
        ).fetchone()[0]
        update_task(
            conn,
            int(consult_id),
            is_done=True,
            form_data={"target_keywords": "seo bất động sản", "current_status": "Traffic thấp"},
            notes="Audit Consult hoàn tất",
        )
        conn.execute(
            "UPDATE crm_svc_tasks SET ai_output = ? WHERE id = ?",
            ("UNIQUE_CONSULT_AI_OUTPUT_FOR_PROPOSAL", int(consult_id)),
        )
        conn.commit()

        ctx = m.get_customer_context(conn, cid, lifecycle_id=lid)
        self.assertIsNotNone(ctx["consult"])
        self.assertEqual(ctx["consult"]["form_data"]["target_keywords"], "seo bất động sản")
        self.assertIn("UNIQUE_CONSULT_AI_OUTPUT_FOR_PROPOSAL", ctx["consult"]["ai_output"])
        self.assertEqual(ctx["consult"]["notes"], "Audit Consult hoàn tất")
        self.assertTrue(ctx["consult"]["is_done"])

    def test_context_consult_none_without_lifecycle(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        ctx = m.get_customer_context(conn, cid)
        self.assertIsNone(ctx["consult"])


class TestRunProposalAi(unittest.TestCase):
    def test_no_api_key_returns_empty_dict(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        pid = m.create_proposal(conn, cid, ["dich-vu-seo-local"], 5000000, 3, "")
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.side_effect = Exception("no key")
            result = m.run_proposal_ai(conn, pid)
        self.assertEqual(result, {})

    def test_mock_saves_and_returns_five_sections(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        pid = m.create_proposal(conn, cid, ["dich-vu-seo-local"], 5000000, 3, "")
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text=(
            "## Phân tích vấn đề\nKhách cần SEO.\n"
            "## Giải pháp đề xuất\nSEO Local giải quyết vấn đề.\n"
            "## Tại sao chọn PTTCOM\nKinh nghiệm 5 năm.\n"
            "## Kết quả kỳ vọng\n- Traffic tăng 50%\n- Top 3 Google\n"
            "## Tóm tắt báo giá\nGiá trị xứng đáng với đầu tư."
        ))]
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_resp
            result = m.run_proposal_ai(conn, pid)
        self.assertIn("problem", result)
        self.assertIn("solution", result)
        self.assertIn("usp", result)
        self.assertIn("kpi", result)
        self.assertIn("pricing_narrative", result)
        row = conn.execute("SELECT ai_output FROM crm_proposals WHERE id = ?", (pid,)).fetchone()
        saved = json.loads(row["ai_output"])
        self.assertIn("problem", saved)
        self.assertNotEqual(saved["problem"], "")

    def test_run_proposal_ai_includes_consult_in_prompt(self):
        from crm_svc_tasks import seed_tasks, update_task

        conn = _setup_conn()
        cid = _seed_customer(conn)
        conn.execute(
            """
            INSERT INTO crm_service_lifecycle (customer_id, service_slug, stage, status)
            VALUES (?, 'dich-vu-seo-tong-the', 'consult', 'active')
            """,
            (cid,),
        )
        lid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        seed_tasks(conn, lifecycle_id=lid, service_slug="dich-vu-seo-tong-the")
        consult_id = conn.execute(
            "SELECT id FROM crm_svc_tasks WHERE lifecycle_id = ? AND stage = 'consult'",
            (lid,),
        ).fetchone()[0]
        update_task(
            conn,
            int(consult_id),
            form_data={"current_status": "Domain mới"},
        )
        conn.execute(
            "UPDATE crm_svc_tasks SET ai_output = ? WHERE id = ?",
            ("Consult scope: 50 keywords/month", int(consult_id)),
        )
        conn.commit()
        pid = m.create_proposal(
            conn,
            cid,
            ["dich-vu-seo-tong-the"],
            5000000,
            3,
            "",
            lifecycle_id=lid,
        )
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text=(
            "## Phân tích vấn đề\nPain.\n"
            "## Giải pháp đề xuất\nSolution.\n"
            "## Tại sao chọn PTTCOM\nUSP.\n"
            "## Kết quả kỳ vọng\n- KPI\n"
            "## Tóm tắt báo giá\nPricing."
        ))]
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_resp
            m.run_proposal_ai(conn, pid)
        prompt = mock_cls.return_value.messages.create.call_args.kwargs["messages"][0]["content"]
        self.assertIn("Consult scope: 50 keywords/month", prompt)
        self.assertIn("Domain mới", prompt)


if __name__ == "__main__":
    unittest.main()
