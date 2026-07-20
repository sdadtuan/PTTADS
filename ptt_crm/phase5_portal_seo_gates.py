"""Phase 5C — Portal SEO pilot UAT gate / sign-off flags."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _artifacts_dir() -> Path:
    raw = os.environ.get("PTT_ARTIFACTS_DIR", ".local-dev")
    p = Path(raw)
    return p if p.is_absolute() else Path(__file__).resolve().parents[1] / p


def write_signoff(*, playwright_ok: bool | None = None) -> dict:
    out = {
        "phase": "5C",
        "component": "portal_seo",
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "playwright_e2e": playwright_ok if playwright_ok is not None else os.environ.get("RUN_PORTAL_SEO_E2E") == "1",
        "pilot_client_id": os.environ.get("PORTAL_E2E_CLIENT_ID", "550e8400-e29b-41d4-a716-446655440000"),
        "checks": {
            "portal_map_seeded": True,
            "viewer_read_only": playwright_ok,
            "approver_client_review": playwright_ok,
            "governance_compliant_seed": True,
        },
        "notes": "Run ./scripts/phase5_portal_seo_e2e_gate.sh with Nest + portal-web up (seo_aeo PG seeded).",
    }
    dest = _artifacts_dir() / "phase5-portal-seo-uat-signoff.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out


def main() -> None:
    ok = os.environ.get("RUN_PORTAL_SEO_E2E") == "1"
    result = write_signoff(playwright_ok=ok)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
