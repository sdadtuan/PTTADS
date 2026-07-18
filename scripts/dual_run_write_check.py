#!/usr/bin/env python3
"""Write dual-run check — PG OLTP vs SQLite shadow vs Nest (Phase 2 W7)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare PG write vs SQLite shadow vs Nest")
    parser.add_argument("--sample", type=int, default=50, help="Number of leads to sample")
    parser.add_argument("--no-nest", action="store_true", help="Skip Nest GET compare")
    parser.add_argument("--quiet", action="store_true", help="Summary line only")
    parser.add_argument("--record", action="store_true", help="Append result to soak evidence log")
    parser.add_argument(
        "--soak-report",
        action="store_true",
        help="Print 48h soak gate summary (exit 1 if gate not passed)",
    )
    args = parser.parse_args()

    from ptt_crm.dual_run_write import run_write_dual_run_check

    report = run_write_dual_run_check(
        sample_size=max(1, args.sample),
        include_nest=not args.no_nest,
    )

    if args.record:
        from ptt_crm.write_soak_evidence import append_soak_record

        append_soak_record(report)

    if args.soak_report:
        from ptt_crm.write_soak_evidence import build_soak_summary

        summary = build_soak_summary()
        if args.quiet:
            gate = summary["gate_48h"]
            status = "OK" if gate["ok"] else "FAIL"
            print(
                f"{status} write-soak-48h span={gate.get('span_hours')}h "
                f"samples={gate.get('ok_sample_count')}/{gate.get('sample_count')} "
                f"reason={gate.get('reason')}"
            )
        else:
            print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
        return 0 if summary["gate_48h"]["ok"] else 1

    if args.quiet:
        status = "OK" if report["ok"] else "FAIL"
        print(
            f"{status} write-dual-run sample={report['sample_size']} "
            f"pg_sqlite={report['pg_sqlite_mismatch_count']} "
            f"pg_nest={report['pg_nest_mismatch_count']}"
        )
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
