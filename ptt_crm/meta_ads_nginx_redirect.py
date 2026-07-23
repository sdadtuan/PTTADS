"""Meta Ads nginx redirect verification — /crm/facebook-ads → ops-web (Horizon 1 B3.4 / M1-G06)."""
from __future__ import annotations

import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from ptt_crm.config import meta_ads_ops_web_hub_path, meta_ads_ops_web_hub_url, ops_web_base_url

ROOT = Path(__file__).resolve().parents[1]

META_LEGACY_PATH = "/crm/facebook-ads"
DEPLOY_NGINX = ROOT / "deploy" / "nginx-rs-delivery-admin-retired.conf"
SNIPPET_NGINX = ROOT / "deploy" / "nginx-meta-ads-retired-snippet.conf"
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def rs_base_url() -> str:
    return (
        os.environ.get("PTT_RS_BASE_URL")
        or os.environ.get("HORIZON1_RS_BASE_URL")
        or "https://rs.pttads.vn"
    ).rstrip("/")


def nginx_rs_site_path() -> Path:
    return Path(os.environ.get("NGINX_RS_SITE", "/etc/nginx/sites-available/rs.pttads.vn"))


def expected_redirect_location() -> str:
    return meta_ads_ops_web_hub_url()


def _nginx_text_has_redirect(text: str) -> bool:
    return META_LEGACY_PATH in text and meta_ads_ops_web_hub_path() in text


def check_deploy_nginx_config() -> dict[str, Any]:
    deploy_ok = False
    snippet_ok = False
    if DEPLOY_NGINX.is_file():
        deploy_ok = _nginx_text_has_redirect(DEPLOY_NGINX.read_text(encoding="utf-8"))
    if SNIPPET_NGINX.is_file():
        snippet_ok = _nginx_text_has_redirect(SNIPPET_NGINX.read_text(encoding="utf-8"))
    ok = deploy_ok or snippet_ok
    return {
        "ok": ok,
        "deploy_file_ok": deploy_ok,
        "snippet_file_ok": snippet_ok,
        "deploy_path": str(DEPLOY_NGINX.relative_to(ROOT)) if DEPLOY_NGINX.is_file() else None,
        "snippet_path": str(SNIPPET_NGINX.relative_to(ROOT)) if SNIPPET_NGINX.is_file() else None,
    }


def check_live_nginx_site() -> dict[str, Any]:
    site = nginx_rs_site_path()
    if not site.is_file():
        return {"ok": None, "skipped": True, "site_path": str(site), "configured": None}
    text = site.read_text(encoding="utf-8", errors="replace")
    configured = _nginx_text_has_redirect(text)
    return {
        "ok": configured,
        "skipped": False,
        "site_path": str(site),
        "configured": configured,
        "has_location_block": "location ^~ /crm/facebook-ads" in text,
    }


def _location_matches_expected(location: str | None, expected: str) -> bool:
    if not location:
        return False
    loc = location.strip()
    if not loc:
        return False
    if loc == expected:
        return True
    exp = urlparse(expected)
    got = urlparse(urljoin(expected, loc) if loc.startswith("/") else loc)
    if got.scheme and exp.scheme and got.scheme != exp.scheme:
        return False
    if got.netloc and exp.netloc and got.netloc.lower() != exp.netloc.lower():
        return False
    exp_path = exp.path.rstrip("/") or "/"
    got_path = got.path.rstrip("/") or "/"
    return got_path == exp_path


def fetch_redirect(
    url: str,
    *,
    timeout: float = 12.0,
    method: str = "HEAD",
) -> dict[str, Any]:
    class _NoFollow(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ARG002
            return None

    opener = urllib.request.build_opener(_NoFollow)
    req = urllib.request.Request(url, method=method)
    try:
        with opener.open(req, timeout=timeout) as resp:
            status = resp.status
            location = resp.headers.get("Location")
    except urllib.error.HTTPError as exc:
        status = exc.code
        location = exc.headers.get("Location") if exc.headers else None
    except Exception as exc:
        return {"url": url, "ok": False, "status": None, "location": None, "error": str(exc)}

    expected = expected_redirect_location()
    ok = status in REDIRECT_STATUSES and _location_matches_expected(location, expected)
    return {
        "url": url,
        "ok": ok,
        "status": status,
        "location": location,
        "expected_location": expected,
        "error": None if ok else "redirect_mismatch",
    }


def verify_live_redirect(*, paths: tuple[str, ...] | None = None) -> dict[str, Any]:
    base = rs_base_url()
    checks: list[dict[str, Any]] = []
    for suffix in paths or (META_LEGACY_PATH, f"{META_LEGACY_PATH}/", f"{META_LEGACY_PATH}?utm=test"):
        url = f"{base}{suffix}" if suffix.startswith("/") else f"{base}/{suffix}"
        checks.append(fetch_redirect(url))
    ok = all(c.get("ok") for c in checks)
    return {
        "ok": ok,
        "rs_base_url": base,
        "expected_location": expected_redirect_location(),
        "checks": checks,
    }


def verify_legacy_routes_unbroken(*, paths: tuple[str, ...] | None = None) -> dict[str, Any]:
    """Ensure other rs.pttads.vn CRM redirects still respond (regression guard)."""
    base = rs_base_url()
    ops = ops_web_base_url()
    checks: list[dict[str, Any]] = []
    for path in paths or ("/crm/leads", "/crm/hub"):
        url = f"{base}{path}"
        result = fetch_redirect(url)
        loc = result.get("location") or ""
        ops_ok = ops.replace("https://", "").replace("http://", "") in loc.replace("https://", "").replace("http://", "")
        checks.append({**result, "ops_redirect_ok": ops_ok and result.get("status") in REDIRECT_STATUSES})
    ok = all(c.get("ops_redirect_ok") for c in checks)
    return {"ok": ok, "checks": checks}


def nginx_redirect_status(*, include_live: bool | None = None) -> dict[str, Any]:
    deploy = check_deploy_nginx_config()
    site = check_live_nginx_site()
    skip_live = _truthy("HORIZON1_SKIP_NGINX_REDIRECT_VERIFY", "1")
    do_live = include_live if include_live is not None else not skip_live
    live: dict[str, Any] | None = None
    if do_live:
        live = verify_live_redirect()
    config_ok = deploy["ok"] and (site["ok"] is not False)
    live_ok = live["ok"] if live is not None else None
    gate_ok = config_ok and (live_ok is not False if live_ok is not None else True)
    return {
        "ok": gate_ok,
        "legacy_path": META_LEGACY_PATH,
        "ops_web_hub_url": expected_redirect_location(),
        "deploy_nginx": deploy,
        "live_nginx_site": site,
        "live_redirect": live,
        "gate_m1_g06": gate_ok,
        "gate_m1_g06_config": config_ok,
        "gate_m1_g06_live": live_ok,
        "live_verify_skipped": not do_live,
    }


def verify_nginx_redirect_gate() -> dict[str, Any]:
    status = nginx_redirect_status()
    return {
        "id": "M1-G06",
        "ok": bool(status["gate_m1_g06"]),
        "label": "nginx /crm/facebook-ads → ops-web redirect",
        "legacy_path": status["legacy_path"],
        "ops_web_hub_url": status["ops_web_hub_url"],
        "deploy_nginx_ok": status["deploy_nginx"]["ok"],
        "live_nginx_site_ok": status["live_nginx_site"].get("ok"),
        "live_redirect_ok": status.get("gate_m1_g06_live"),
        "live_verify_skipped": status["live_verify_skipped"],
        "live_redirect": status.get("live_redirect"),
        "path": str(DEPLOY_NGINX.relative_to(ROOT)) if DEPLOY_NGINX.is_file() else None,
    }
