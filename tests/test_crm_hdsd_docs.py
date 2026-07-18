"""Tests: HDSD docs catalog."""
from __future__ import annotations

import unittest

from crm_hdsd_docs import list_hdsd_catalog, read_hdsd_doc, resolve_hdsd_doc


class TestHdsdDocs(unittest.TestCase):
    def test_catalog_lists_crm_docs(self) -> None:
        catalog = list_hdsd_catalog()
        crm = next(g for g in catalog if g["key"] == "crm")
        slugs = {d["slug"] for d in crm["docs"]}
        self.assertIn("huong-dan-day-du-lead-den-cham-soc-khach-hang", slugs)
        self.assertIn("huong-dan-nguon-lead-va-setup", slugs)

    def test_read_main_guide(self) -> None:
        loaded = read_hdsd_doc("crm", "huong-dan-day-du-lead-den-cham-soc-khach-hang")
        self.assertIsNotNone(loaded)
        text, meta = loaded
        self.assertIn("Lead", text)
        self.assertEqual(meta["section"], "crm")

    def test_reject_path_traversal(self) -> None:
        self.assertIsNone(resolve_hdsd_doc("crm", "../secrets"))
        self.assertIsNone(resolve_hdsd_doc("..", "etc-passwd"))


if __name__ == "__main__":
    unittest.main()
