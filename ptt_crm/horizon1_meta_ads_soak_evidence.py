"""Horizon 1 — Meta Ads migration soak snapshots."""
from __future__ import annotations

import json
import os
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_SOAK_LOG = Path(".local-dev/horizon1-meta-ads-soak-evidence.jsonl")
DEFAULT_REQUIRED_DAYS = 7
DEFAULT_MIN_SAMPLES = 7


def soak_log_path() -> Path:
    raw = (os.environ.get("PTT_HORIZON1_SOAK_LOG") or "").strip()
    return Path(raw) if raw else DEFAULT_SOAK_LOG


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(value: str) -> datetime | None:
    try:
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _flag(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


def collect_snapshot(*, hours: int = 24) -> dict[str, Any]:
    snap: dict[str, Any] = {
        "recorded_at": _utc_now().replace(microsecond=0).isoformat(),
        "host": socket.gethostname(),
        "ok": True,
        "flags": {
            "PTT_WEBHOOKS_NEST_META": _flag("PTT_WEBHOOKS_NEST_META", "1"),
            "PTT_WEBHOOKS_FLASK_FALLBACK": _flag("PTT_WEBHOOKS_FLASK_FALLBACK", "0"),
            "PTT_FLASK_META_ADS_ADMIN_RETIRED": _flag("PTT_FLASK_META_ADS_ADMIN_RETIRED", "0"),
        },
        "metrics": {},
    }
    db_url = (os.environ.get("DATABASE_URL") or "").strip()
    if not db_url:
        snap["ok"] = False
        snap["db_error"] = "DATABASE_URL missing"
        return snap
    try:
        import psycopg2

        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM job_queue
               WHERE job_type LIKE 'lead%%' AND created_at >= NOW() - (%s || ' hours')::interval) AS lead_jobs_24h,
              (SELECT COUNT(*) FROM daily_performance
               WHERE channel = 'meta' AND performance_date >= CURRENT_DATE - 7) AS meta_perf_rows_7d,
              (SELECT COUNT(*) FROM client_channel_accounts
               WHERE channel = 'meta' AND access_token_encrypted IS NOT NULL) AS meta_tokens
            """,
            (str(max(1, hours)),),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            snap["metrics"] = {
                "lead_jobs_24h": int(row[0] or 0),
                "meta_perf_rows_7d": int(row[1] or 0),
                "meta_tokens_active": int(row[2] or 0),
            }
    except Exception as exc:
        snap["ok"] = False
        snap["db_error"] = str(exc)
    if _flag("PTT_WEBHOOKS_FLASK_FALLBACK", "0"):
        snap["ok"] = snap.get("ok", True) and not _flag("PTT_WEBHOOKS_FLASK_FALLBACK")
    return snap


def append_soak_record(snapshot: dict[str, Any] | None = None, *, path: Path | None = None) -> dict[str, Any]:
    record = snapshot or collect_snapshot()
    log_path = path or soak_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return record


def load_soak_records(*, path: Path | None = None, since_days: float | None = None) -> list[dict[str, Any]]:
    log_path = path or soak_log_path()
    if not log_path.is_file():
        return []
    cutoff = None
    if since_days is not None:
        cutoff = _utc_now() - timedelta(days=max(0.0, since_days))
    out: list[dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = _parse_ts(str(row.get("recorded_at") or ""))
        if cutoff and ts and ts < cutoff:
            continue
        out.append(row)
    return out


def evaluate_soak_gate(
    *,
    path: Path | None = None,
    required_days: float | None = None,
    min_samples: int | None = None,
) -> dict[str, Any]:
    required_days = float(
        required_days if required_days is not None else os.environ.get("PTT_HORIZON1_SOAK_DAYS", DEFAULT_REQUIRED_DAYS)
    )
    min_samples = int(
        min_samples if min_samples is not None else os.environ.get("PTT_HORIZON1_SOAK_MIN_SAMPLES", DEFAULT_MIN_SAMPLES)
    )
    records = load_soak_records(path=path, since_days=required_days + 1)
    if not records:
        return {
            "ok": False,
            "label": "Horizon 1 Meta soak",
            "error": "no_records",
            "required_days": required_days,
            "min_samples": min_samples,
            "sample_count": 0,
        }
    timestamps = [_parse_ts(str(r.get("recorded_at") or "")) for r in records]
    timestamps = [t for t in timestamps if t is not None]
    if not timestamps:
        return {"ok": False, "label": "Horizon 1 Meta soak", "error": "invalid_timestamps"}
    span_days = (max(timestamps) - min(timestamps)).total_seconds() / 86400.0
    failures = [r for r in records if not r.get("ok", True)]
    ok = span_days >= required_days and len(records) >= min_samples and not failures
    return {
        "ok": ok,
        "label": "Horizon 1 Meta soak",
        "span_days": round(span_days, 2),
        "required_days": required_days,
        "sample_count": len(records),
        "min_samples": min_samples,
        "failure_count": len(failures),
        "latest": records[-1],
    }


def main() -> None:
    import sys

    cmd = (sys.argv[1] if len(sys.argv) > 1 else "record").strip().lower()
    if cmd == "evaluate":
        print(json.dumps(evaluate_soak_gate(), indent=2))
        return
    rec = append_soak_record()
    print(json.dumps(rec, indent=2))


if __name__ == "__main__":
    main()
