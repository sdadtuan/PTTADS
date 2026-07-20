#!/usr/bin/env python3
"""Staging Phase 5 gate pack — Flask retirement readiness."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 5 Flask retirement staging gates")
    parser.add_argument("--skip-seo-gates", action="store_true", help="Skip SEO Phase 5 governance gates")
    parser.add_argument(
        "--report",
        default=str(ROOT / ".local-dev" / "staging-phase5-gate-report.json"),
    )
    args = parser.parse_args()

    from ptt_crm.phase5_flask_retirement_gates import run_gates as run_retire_gates

    steps: dict[str, object] = {}
    retire = run_retire_gates()
    steps["flask_retirement"] = {"ok": retire.get("ok"), "report": retire}

    if not args.skip_seo_gates:
        import os

        os.environ.setdefault("PHASE5_SKIP_SOAK", "1")
        os.environ.setdefault("PHASE5_SKIP_PORTAL_SIGNOFF", "1")
        from ptt_crm.phase5_prod_gates import run_gates as run_seo_gates

        seo = run_seo_gates()
        steps["seo_phase5"] = {"ok": seo.get("ok"), "report": seo}

    ok = all(bool(v.get("ok")) for v in steps.values() if isinstance(v, dict))
    report = {
        "phase": "5-staging",
        "ok": ok,
        "steps": steps,
        "notes": "Prod cutover: APPLY=1 sudo -E ./scripts/close_flask_retirement.sh",
    }
    path = Path(args.report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str)[:8000])
    print("")
    if ok:
        print(f"OK  Phase 5 staging gate pack — {path}")
        return 0
    print(f"FAIL Phase 5 staging gate pack — {path}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
