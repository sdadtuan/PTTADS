#!/usr/bin/env python3
"""Unit tests — Meta Ads nginx redirect verification (B3.4 / M1-G06)."""
from __future__ import annotations

import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from ptt_crm.meta_ads_nginx_redirect import (
    _location_matches_expected,
    check_deploy_nginx_config,
    check_live_nginx_site,
    fetch_redirect,
    nginx_redirect_status,
    verify_nginx_redirect_gate,
)


class LocationMatchTests(unittest.TestCase):
    def test_exact_match(self) -> None:
        exp = "https://ops.pttads.vn/meta/facebook-ads"
        self.assertTrue(_location_matches_expected(exp, exp))

    def test_relative_path(self) -> None:
        exp = "https://ops.pttads.vn/meta/facebook-ads"
        self.assertTrue(_location_matches_expected("/meta/facebook-ads", exp))


class DeployNginxConfigTests(unittest.TestCase):
    def test_deploy_config_present(self) -> None:
        out = check_deploy_nginx_config()
        self.assertTrue(out["ok"])
        self.assertTrue(out["deploy_file_ok"] or out["snippet_file_ok"])


class LiveNginxSiteTests(unittest.TestCase):
    def test_missing_site_skipped(self) -> None:
        with patch.dict(os.environ, {"NGINX_RS_SITE": "/nonexistent/rs.pttads.vn"}, clear=False):
            out = check_live_nginx_site()
        self.assertIsNone(out["ok"])
        self.assertTrue(out["skipped"])

    def test_site_with_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "rs.pttads.vn"
            site.write_text(
                "location ^~ /crm/facebook-ads {\n"
                "    return 302 https://ops.pttads.vn/meta/facebook-ads;\n"
                "}\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"NGINX_RS_SITE": str(site)}, clear=False):
                out = check_live_nginx_site()
            self.assertTrue(out["ok"])
            self.assertTrue(out["configured"])


class FetchRedirectTests(unittest.TestCase):
    def test_redirect_ok(self) -> None:
        class FakeResp:
            status = 302
            headers = {"Location": "https://ops.pttads.vn/meta/facebook-ads"}

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with patch.dict(os.environ, {"PTT_OPS_WEB_URL": "https://ops.pttads.vn"}, clear=False), patch(
            "urllib.request.OpenerDirector.open", return_value=FakeResp()
        ):
            out = fetch_redirect("https://rs.pttads.vn/crm/facebook-ads")
        self.assertTrue(out["ok"])
        self.assertEqual(out["status"], 302)

    def test_wrong_location(self) -> None:
        class FakeExc(urllib.error.HTTPError):
            def __init__(self):
                super().__init__(
                    url="https://rs.pttads.vn/crm/facebook-ads",
                    code=302,
                    msg="Found",
                    hdrs={"Location": "https://example.com/wrong"},
                    fp=None,
                )

        with patch("urllib.request.OpenerDirector.open", side_effect=FakeExc()):
            out = fetch_redirect("https://rs.pttads.vn/crm/facebook-ads")
        self.assertFalse(out["ok"])


class GateTests(unittest.TestCase):
    def test_gate_skips_live_by_default(self) -> None:
        with patch.dict(os.environ, {"HORIZON1_SKIP_NGINX_REDIRECT_VERIFY": "1"}, clear=False):
            status = nginx_redirect_status()
            gate = verify_nginx_redirect_gate()
        self.assertTrue(status["live_verify_skipped"])
        self.assertTrue(status["gate_m1_g06_config"])
        self.assertTrue(gate["ok"])
        self.assertEqual(gate["id"], "M1-G06")

    def test_gate_live_required_when_enabled(self) -> None:
        with patch.dict(
            os.environ,
            {"HORIZON1_SKIP_NGINX_REDIRECT_VERIFY": "0", "PTT_RS_BASE_URL": "https://rs.test"},
            clear=False,
        ), patch(
            "ptt_crm.meta_ads_nginx_redirect.verify_live_redirect",
            return_value={"ok": False, "checks": []},
        ):
            gate = verify_nginx_redirect_gate()
        self.assertFalse(gate["ok"])
