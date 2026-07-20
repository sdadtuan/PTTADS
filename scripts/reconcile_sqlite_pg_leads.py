#!/usr/bin/env python3
"""Reconcile SQLite vs PostgreSQL crm_leads counts (Sprint 0 S0-9)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _pct_diff(a: int, b: int) -> float:
    if a == 0 and b == 0:
        return 0.0
    base = max(a, b, 1)
    return abs(a - b) / base * 100.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile SQLite vs PG lead counts")
    parser.add_argument("--sample", type=int, default=100, help="Sample size for fingerprint diff")
    parser.add_argument(
        "--max-pct-diff",
        type=float,
        default=0.1,
        help="Fail if count difference exceeds this percent (default 0.1)",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON only")
    args = parser.parse_args()

    from ptt_crm.lead_sync import reconcile_leads

    report = reconcile_leads(sample_size=max(1, args.sample))
    sqlite_total = int(report.get("sqlite_total") or 0)
    pg_total = int(report.get("pg_total") or 0)
    pct = _pct_diff(sqlite_total, pg_total)
    count_ok = pct <= args.max_pct_diff
    sample_ok = bool(report.get("ok"))
    report["count_pct_diff"] = round(pct, 4)
    report["count_within_threshold"] = count_ok
    report["ok"] = count_ok and sample_ok and int(report.get("mismatch_count") or 0) == 0

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"SQLite total: {sqlite_total}")
        print(f"PG total:     {pg_total}")
        print(f"Count diff:   {pct:.4f}% (threshold {args.max_pct_diff}%)")
        print(f"Sample mismatches: {report.get('mismatch_count', 0)}")
        print(f"OK: {report['ok']}")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
