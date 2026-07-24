"""B9 — Meta tracking / CAPI pilot soak snapshots."""
from __future__ import annotations

import json
import os
import socket
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_SOAK_LOG = Path(".local-dev/b9-tracking-soak-evidence.jsonl")
DEFAULT_REQUIRED_DAYS = 30
DEFAULT_MIN_SAMPLES = 28


def soak_log_path() -> Path:
    raw = (os.environ.get("PTT_B9_SOAK_LOG") or "").strip()
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


def _pilot_client_ids() -> list[str]:
    raw = (os.environ.get("PTT_CAPI_PILOT_CLIENTS") or "").strip()
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def collect_snapshot(*, hours: int = 24) -> dict[str, Any]:
    snap: dict[str, Any] = {
        "recorded_at": _utc_now().replace(microsecond=0).isoformat(),
        "host": socket.gethostname(),
        "ok": True,
        "flags": {
            "PTT_META_TRACKING_ENABLED": _flag("PTT_META_TRACKING_ENABLED", "0"),
            "PTT_CAPI_ENABLED": _flag("PTT_CAPI_ENABLED", "0"),
            "PTT_CAPI_STUB": _flag("PTT_CAPI_STUB", "0"),
            "PTT_META_CONVERSION_SYNC_ENABLED": _flag("PTT_META_CONVERSION_SYNC_ENABLED", "0"),
            "PTT_LAUNCH_QA_META_STRICT": _flag("PTT_LAUNCH_QA_META_STRICT", "0"),
        },
        "pilot_clients": _pilot_client_ids(),
        "metrics": {},
        "thresholds": {
            "max_fail_rate_pct": float(os.environ.get("PTT_B9_SOAK_MAX_FAIL_RATE_PCT", "10")),
            "min_sent_24h": int(os.environ.get("PTT_B9_SOAK_MIN_SENT_24H", "1")),
        },
        "violations": [],
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
        pilots = _pilot_client_ids()
        window = str(max(1, hours))

        if pilots:
            cur.execute(
                """
                SELECT
                  (SELECT COUNT(*) FROM capi_event_log
                   WHERE status = 'sent'
                     AND sent_at >= NOW() - (%s || ' hours')::interval
                     AND client_id = ANY(%s::uuid[])) AS sent_24h,
                  (SELECT COUNT(*) FROM capi_event_log
                   WHERE status = 'failed'
                     AND created_at >= NOW() - (%s || ' hours')::interval
                     AND client_id = ANY(%s::uuid[])) AS failed_24h,
                  (SELECT COUNT(*) FROM capi_event_log
                   WHERE status IN ('pending', 'skipped')
                     AND created_at >= NOW() - (24 || ' hours')::interval
                     AND client_id = ANY(%s::uuid[])) AS other_24h,
                  (SELECT COUNT(*) FROM launch_qa_runs
                   WHERE status = 'in_progress'
                     AND checklist ? 'meta_pixel_configured') AS launch_qa_meta_runs,
                  (SELECT COUNT(*) FROM launch_qa_runs
                   WHERE launch_ready = FALSE
                     AND status = 'in_progress'
                     AND checklist ? 'meta_capi_test_ok') AS launch_qa_blocked_meta
                """,
                (window, pilots, window, pilots, pilots),
            )
        else:
            cur.execute(
                """
                SELECT
                  (SELECT COUNT(*) FROM capi_event_log
                   WHERE status = 'sent'
                     AND sent_at >= NOW() - (%s || ' hours')::interval) AS sent_24h,
                  (SELECT COUNT(*) FROM capi_event_log
                   WHERE status = 'failed'
                     AND created_at >= NOW() - (%s || ' hours')::interval) AS failed_24h,
                  (SELECT COUNT(*) FROM capi_event_log
                   WHERE status IN ('pending', 'skipped')
                     AND created_at >= NOW() - (24 || ' hours')::interval) AS other_24h,
                  (SELECT COUNT(*) FROM launch_qa_runs
                   WHERE status = 'in_progress'
                     AND checklist ? 'meta_pixel_configured') AS launch_qa_meta_runs,
                  (SELECT COUNT(*) FROM launch_qa_runs
                   WHERE launch_ready = FALSE
                     AND status = 'in_progress'
                     AND checklist ? 'meta_capi_test_ok') AS launch_qa_blocked_meta
                """,
                (window, window),
            )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            sent = int(row[0] or 0)
            failed = int(row[1] or 0)
            denom = sent + failed
            fail_rate = (failed / denom * 100.0) if denom else 0.0
            snap["metrics"] = {
                "capi_sent_24h": sent,
                "capi_failed_24h": failed,
                "capi_other_24h": int(row[2] or 0),
                "capi_fail_rate_pct": round(fail_rate, 2),
                "launch_qa_meta_runs": int(row[3] or 0),
                "launch_qa_blocked_meta": int(row[4] or 0),
            }
            max_fail = float(snap["thresholds"]["max_fail_rate_pct"])
            min_sent = int(snap["thresholds"]["min_sent_24h"])
            if _flag("PTT_CAPI_ENABLED", "0") and not _flag("PTT_CAPI_STUB", "0"):
                if denom and fail_rate > max_fail:
                    snap["violations"].append(f"capi_fail_rate_pct>{max_fail}")
                    snap["ok"] = False
                if sent < min_sent and pilots:
                    snap["violations"].append(f"capi_sent_24h<{min_sent}")
                    snap["ok"] = False
    except Exception as exc:
        snap["ok"] = False
        snap["db_error"] = str(exc)
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
        required_days if required_days is not None else os.environ.get("PTT_B9_SOAK_DAYS", DEFAULT_REQUIRED_DAYS)
    )
    min_samples = int(
        min_samples if min_samples is not None else os.environ.get("PTT_B9_SOAK_MIN_SAMPLES", DEFAULT_MIN_SAMPLES)
    )
    records = load_soak_records(path=path, since_days=required_days + 1)
    if not records:
        return {
            "ok": False,
            "label": "B9 tracking pilot soak",
            "error": "no_records",
            "required_days": required_days,
            "min_samples": min_samples,
            "sample_count": 0,
            "hint": "./scripts/b9_tracking_soak_record.sh",
        }
    timestamps = [_parse_ts(str(r.get("recorded_at") or "")) for r in records]
    timestamps = [t for t in timestamps if t is not None]
    if not timestamps:
        return {"ok": False, "label": "B9 tracking pilot soak", "error": "invalid_timestamps"}
    span_days = (max(timestamps) - min(timestamps)).total_seconds() / 86400.0
    failures = [r for r in records if not r.get("ok", True)]
    ok = span_days >= required_days and len(records) >= min_samples and not failures
    return {
        "ok": ok,
        "label": "B9 tracking pilot soak",
        "span_days": round(span_days, 2),
        "required_days": required_days,
        "sample_count": len(records),
        "min_samples": min_samples,
        "failure_count": len(failures),
        "log_path": str(path or soak_log_path()),
    }


def main(argv: list[str] | None = None) -> int:
    cmd = (argv or sys.argv[1:2] or ["record"])[0]
    if cmd == "record":
        rec = append_soak_record()
        print(json.dumps({"ok": rec.get("ok", True), "recorded_at": rec.get("recorded_at")}, ensure_ascii=False))
        return 0 if rec.get("ok", True) else 1
    if cmd == "evaluate":
        result = evaluate_soak_gate()
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    print("Usage: b9_tracking_soak_evidence.py [record|evaluate]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
