#!/usr/bin/env python3
"""CLI — staging closed-loop pilot for 1 client (P0 #4)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Closed-loop pilot — token + pixel + map + insights → CPL")
    parser.add_argument("--client-code", default="", help="Agency client code (e.g. DEMO)")
    parser.add_argument("--client-id", default="", help="Agency client UUID")
    parser.add_argument("--sync", action="store_true", help="Run Meta insights sync before verify")
    parser.add_argument("--report", default=str(ROOT / ".local-dev" / "closed-loop-pilot-report.json"))
    parser.add_argument("--min-maps", type=int, default=1)
    parser.add_argument("--min-rows", type=int, default=1)
    args = parser.parse_args()

    from ptt_agency.closed_loop_pilot import run_closed_loop_pilot

    report = run_closed_loop_pilot(
        client_id=args.client_id.strip() or None,
        client_code=args.client_code.strip() or None,
        run_sync=args.sync,
        min_hub_maps=max(1, args.min_maps),
        min_perf_rows=max(1, args.min_rows),
    )

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    print(json.dumps(report, indent=2, ensure_ascii=False, default=str)[:8000])

    if report.get("ok"):
        cpl = (report.get("steps") or {}).get("cpl_tab") or {}
        summary = cpl.get("summary") or {}
        print("")
        print(f"OK  closed-loop pilot — CPL rows={summary.get('row_count', cpl.get('row_count'))}")
        print(f"    UI: {cpl.get('ui_path', '/crm/agency/clients')}")
        print(f"    Report: {report_path}")
        return 0

    print("")
    print(f"FAIL closed-loop pilot — {report.get('failed_steps')} — {report_path}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
