"""P4 — Flask blueprints + route registration."""
from __future__ import annotations


import os
import unittest

if os.environ.get("PTT_RUN_FLASK_TESTS") != "1":
    raise unittest.SkipTest(
        "Flask HTTP removed — set PTT_RUN_FLASK_TESTS=1 to run integration tests"
    )
import unittest


class CrmP4BlueprintTest(unittest.TestCase):
    def test_product_model_routes_registered(self) -> None:
        import app as app_module

        rules = {rule.rule for rule in app_module.app.url_map.iter_rules()}
        expected = {
            "/api/crm/catalog",
            "/crm/catalog",
            "/api/crm/assign-scopes",
            "/api/crm/leads/review-queue/sync",
            "/api/crm/leads/<int:lead_id>/review-queue/release",
            "/api/crm/leads/<int:lead_id>/industry-addon",
            "/api/crm/leads/<int:lead_id>/presales/marketing-plan",
            "/api/crm/service-lifecycle/<int:lifecycle_id>/marketing-plan",
        }
        missing = expected - rules
        self.assertFalse(missing, f"Missing routes: {missing}")

    def test_legacy_endpoint_aliases(self) -> None:
        import app as app_module

        endpoints = set(app_module.app.view_functions)
        self.assertIn("crm_catalog_page", endpoints)
        self.assertIn("api_crm_catalog_public", endpoints)


if __name__ == "__main__":
    unittest.main()
