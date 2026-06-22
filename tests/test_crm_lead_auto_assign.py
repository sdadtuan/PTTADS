"""Tests — tự động phân lead theo từng phương pháp (tài liệu nghiệp vụ)."""
from __future__ import annotations

import sqlite3
import unittest
from datetime import datetime

from crm_lead_auto_assign import (
    LeadAssignContext,
    STRATEGY_DEFS,
    auto_assign_lead_owner,
    config_with_only,
    merge_assign_config,
    merge_assign_strategies,
)
from crm_lead_rules import save_lead_config
from crm_lead_store import assign_lead_owner, ensure_lead_schema

TS = "2026-06-04 10:00:00"


def _staff_level(conn: sqlite3.Connection, sid: int) -> str:
    row = conn.execute("SELECT sales_level FROM crm_staff WHERE id = ?", (sid,)).fetchone()
    return str(row["sales_level"])


class AutoAssignTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_lead_schema(self.conn)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS crm_staff (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                sales_level TEXT NOT NULL DEFAULT ''
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS crm_assignment_state (
                pool_key TEXT PRIMARY KEY,
                last_staff_id INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self.staff_ids: dict[str, int] = {}
        staff = [
            ("Minh S", "vip q.7 căn hộ chung cư", "s"),
            ("Lan A", "q.2 nhà phố facebook", "a"),
            ("Binh B", "q.9 warm biệt thự", "b"),
            ("Cuong C", "cold automation nuôi dưỡng", "c"),
            ("Dung A", "q.7 căn hộ việt kiều english", "a"),
        ]
        for name, notes, lv in staff:
            cur = self.conn.execute(
                "INSERT INTO crm_staff (name, notes, active, sales_level) VALUES (?, ?, 1, ?)",
                (name, notes, lv),
            )
            self.staff_ids[name] = int(cur.lastrowid)
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()

    def _assign(self, ctx: LeadAssignContext, *enabled: str):
        cfg = config_with_only(*enabled)
        return auto_assign_lead_owner(self.conn, ctx, config=cfg)

    def _seed_leads(self, owner_id: int, *, open_count: int = 0, won: int = 0, lost: int = 0) -> None:
        n = 0
        for _ in range(open_count):
            n += 1
            self.conn.execute(
                """
                INSERT INTO crm_leads (
                    full_name, phone, phone_norm, email, email_norm, source,
                    lead_score, lead_level, status, owner_id, is_duplicate,
                    status_entered_at, created_at, updated_at, created_by, updated_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, 't', 't')
                """,
                (
                    f"Lead {owner_id}-{n}",
                    f"090{owner_id}{n:04d}",
                    f"090{owner_id}{n:04d}",
                    "",
                    "",
                    "manual",
                    50,
                    "warm",
                    "new",
                    owner_id,
                    TS,
                    TS,
                    TS,
                ),
            )
        for status, cnt in (("won", won), ("lost", lost)):
            for _ in range(cnt):
                n += 1
                self.conn.execute(
                    """
                    INSERT INTO crm_leads (
                        full_name, phone, phone_norm, email, email_norm, source,
                        lead_score, lead_level, status, owner_id, is_duplicate,
                        status_entered_at, created_at, updated_at, created_by, updated_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, 't', 't')
                    """,
                    (
                        f"Lead {owner_id}-{n}",
                        f"091{owner_id}{n:04d}",
                        f"091{owner_id}{n:04d}",
                        "",
                        "",
                        "manual",
                        50,
                        "warm",
                        status,
                        owner_id,
                        TS,
                        TS,
                        TS,
                    ),
                )
        self.conn.commit()


class TestStrategyDefinitions(AutoAssignTestBase):
    def test_strategy_defs_count(self) -> None:
        self.assertGreaterEqual(len(STRATEGY_DEFS), 6)
        ids = {s["id"] for s in STRATEGY_DEFS}
        for sid in (
            "round_robin",
            "skill_based",
            "hybrid",
            "region_product",
            "performance",
            "customer_profile",
        ):
            self.assertIn(sid, ids)


class TestMethod1RoundRobin(AutoAssignTestBase):
    """PP1: Round Robin — luân phiên trong pool."""

    def test_round_robin_rotates_among_all_staff(self) -> None:
        ctx = LeadAssignContext(lead_level="warm", lead_score=40)
        ids = []
        for _ in range(3):
            sid, _, strategy = self._assign(ctx, "round_robin")
            self.assertEqual(strategy, "round_robin")
            ids.append(sid)
        self.assertEqual(len(set(ids)), 3)


class TestMethod2SkillBased(AutoAssignTestBase):
    """PP2: Phân theo năng lực — tier → level NV."""

    def test_hot_assigns_level_s_or_a(self) -> None:
        sid, _, strategy = self._assign(
            LeadAssignContext(lead_level="hot", lead_score=80),
            "skill_based",
        )
        self.assertEqual(strategy, "skill_based")
        self.assertIn(_staff_level(self.conn, sid), ("s", "a"))

    def test_warm_assigns_level_b_or_c(self) -> None:
        sid, _, _ = self._assign(
            LeadAssignContext(lead_level="warm", lead_score=40),
            "skill_based",
        )
        self.assertIn(_staff_level(self.conn, sid), ("b", "c"))

    def test_cold_assigns_level_c(self) -> None:
        sid, _, _ = self._assign(
            LeadAssignContext(lead_level="cold", lead_score=5),
            "skill_based",
            "cold_to_level_c",
        )
        self.assertEqual(_staff_level(self.conn, sid), "c")

    def test_vip_only_s_or_a(self) -> None:
        sid, _, strategy = self._assign(
            LeadAssignContext(lead_level="vip", lead_score=95),
            "vip_to_level_s",
            "skill_based",
        )
        self.assertIn(strategy, ("vip_to_level_s", "skill_based"))
        self.assertIn(_staff_level(self.conn, sid), ("s", "a"))


class TestMethod3RegionProduct(AutoAssignTestBase):
    """PP3: Khu vực / sản phẩm — lọc NV có ghi chú trùng."""

    def test_region_q7_assigns_dung_or_minh(self) -> None:
        sid, _, strategy = self._assign(
            LeadAssignContext(lead_level="warm", lead_score=40, region="q.7"),
            "region_product",
            "round_robin",
        )
        self.assertEqual(strategy, "round_robin")
        self.assertIn(sid, (self.staff_ids["Minh S"], self.staff_ids["Dung A"]))

    def test_product_can_ho_matches_notes(self) -> None:
        sid, _, _ = self._assign(
            LeadAssignContext(
                lead_level="warm",
                lead_score=40,
                product_interest="căn hộ",
            ),
            "region_product",
            "round_robin",
        )
        self.assertIn(sid, (self.staff_ids["Minh S"], self.staff_ids["Dung A"]))


class TestMethod4Performance(AutoAssignTestBase):
    """PP4: Hiệu suất — NV chốt cao được ưu tiên."""

    def test_performance_picks_high_closer(self) -> None:
        # Lan A: 3 won / 3 total; Cuong C: 0 won
        self._seed_leads(self.staff_ids["Lan A"], open_count=0, won=3)
        self._seed_leads(self.staff_ids["Cuong C"], open_count=0, won=0, lost=3)
        sid, _, strategy = self._assign(
            LeadAssignContext(lead_level="warm", lead_score=45),
            "performance",
        )
        self.assertEqual(strategy, "performance")
        self.assertEqual(sid, self.staff_ids["Lan A"])


class TestMethod5CustomerProfile(AutoAssignTestBase):
    """PP5: Đặc điểm KH — match nhu cầu với ghi chú NV."""

    def test_viet_kieu_assigns_dung(self) -> None:
        sid, _, strategy = self._assign(
            LeadAssignContext(
                lead_level="hot",
                lead_score=78,
                need="Khách việt kiều cần tư vấn tiếng Anh",
            ),
            "customer_profile",
        )
        self.assertEqual(strategy, "customer_profile")
        self.assertEqual(sid, self.staff_ids["Dung A"])


class TestMethod6Hybrid(AutoAssignTestBase):
    """PP6: Hybrid — lọc năng lực + Round Robin trong nhóm."""

    def test_hybrid_hot_rotates_s_and_a(self) -> None:
        ctx = LeadAssignContext(lead_level="hot", lead_score=85)
        ids = []
        for _ in range(4):
            sid, _, strategy = self._assign(ctx, "hybrid")
            self.assertEqual(strategy, "hybrid")
            self.assertIn(_staff_level(self.conn, sid), ("s", "a"))
            ids.append(sid)
        self.assertGreater(len(set(ids)), 1)

    def test_hybrid_does_not_use_min_load_for_hot(self) -> None:
        """Hybrid bật thì Hot dùng RR, không dùng hot_priority_min_load."""
        self._seed_leads(self.staff_ids["Minh S"], open_count=5)
        self._seed_leads(self.staff_ids["Lan A"], open_count=0)
        sid, _, strategy = self._assign(
            LeadAssignContext(lead_level="hot", lead_score=80),
            "hybrid",
            "hot_priority_min_load",
        )
        self.assertEqual(strategy, "hybrid")
        # RR trong nhóm S/A — không ép Lan A chỉ vì ít tải
        self.assertIn(_staff_level(self.conn, sid), ("s", "a"))


class TestHotPriorityMinLoad(AutoAssignTestBase):
    def test_hot_min_load_without_hybrid(self) -> None:
        self._seed_leads(self.staff_ids["Minh S"], open_count=4)
        self._seed_leads(self.staff_ids["Lan A"], open_count=0)
        sid, _, strategy = self._assign(
            LeadAssignContext(lead_level="hot", lead_score=80),
            "skill_based",
            "hot_priority_min_load",
        )
        self.assertEqual(strategy, "hot_priority_min_load")
        self.assertEqual(sid, self.staff_ids["Lan A"])


class TestDailyCap(AutoAssignTestBase):
    def test_respect_daily_cap_skips_saturated(self) -> None:
        # Level S max 15/ngày — giả lập Minh S đã nhận đủ hôm nay
        sid_s = self.staff_ids["Minh S"]
        prefix = datetime.now().strftime("%Y-%m-%d")
        for i in range(16):
            self.conn.execute(
                """
                INSERT INTO crm_leads (
                    full_name, phone, phone_norm, email, email_norm, source,
                    lead_score, lead_level, status, owner_id, is_duplicate,
                    status_entered_at, created_at, updated_at, created_by, updated_by
                ) VALUES (?, ?, ?, '', '', 'manual', 90, 'vip', 'new', ?, 0, ?, ?, ?, 't', 't')
                """,
                (f"Cap {i}", f"092{i:05d}", f"092{i:05d}", sid_s, prefix, prefix, prefix),
            )
        self.conn.commit()
        sid, _, strategy = self._assign(
            LeadAssignContext(lead_level="vip", lead_score=95),
            "hybrid",
            "respect_daily_cap",
        )
        self.assertEqual(strategy, "hybrid")
        self.assertNotEqual(sid, sid_s)
        self.assertIn(_staff_level(self.conn, sid), ("s", "a"))


class TestConfigPersistence(AutoAssignTestBase):
    def test_disable_auto_assign(self) -> None:
        cfg = merge_assign_config({"auto_assign_enabled": False})
        sid, _, strategy = auto_assign_lead_owner(
            self.conn, LeadAssignContext(lead_level="hot"), config=cfg
        )
        self.assertIsNone(sid)
        self.assertEqual(strategy, "disabled")

    def test_save_assign_config(self) -> None:
        saved = save_lead_config(
            self.conn,
            config={
                "assign_config": {
                    "auto_assign_enabled": True,
                    "strategies": [
                        {"id": "performance", "enabled": True, "priority": 50},
                        {"id": "round_robin", "enabled": False, "priority": 30},
                    ],
                }
            },
            updated_by="test",
            ts=TS,
        )
        perf = next(s for s in saved["assign_config"]["strategies"] if s["id"] == "performance")
        rr = next(s for s in saved["assign_config"]["strategies"] if s["id"] == "round_robin")
        self.assertTrue(perf["enabled"])
        self.assertFalse(rr["enabled"])

    def test_merge_assign_strategies(self) -> None:
        merged = merge_assign_strategies([{"id": "round_robin", "enabled": False}])
        rr = next(s for s in merged if s["id"] == "round_robin")
        self.assertFalse(rr["enabled"])


class TestIntegration(AutoAssignTestBase):
    def test_assign_lead_owner_default_config(self) -> None:
        sid, name, _strategy = assign_lead_owner(
            self.conn, lead_level="hot", lead_score=80, region="q.2"
        )
        self.assertIsNotNone(sid)
        self.assertTrue(name)
        self.assertIn(_staff_level(self.conn, sid), ("s", "a", "b"))


if __name__ == "__main__":
    unittest.main()
