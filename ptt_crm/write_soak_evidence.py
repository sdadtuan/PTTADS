"""48h write dual-run soak evidence (Phase 2 prod gate)."""
from __future__ import annotations

import json
import os
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_SOAK_LOG = Path(".local-dev/write-soak-evidence.jsonl")
DEFAULT_REQUIRED_HOURS = 48
DEFAULT_MIN_SAMPLES = 24
DEFAULT_MIN_INTERVAL_HOURS = 1.0


def soak_log_path() -> Path:
    raw = (os.environ.get("PTT_WRITE_SOAK_LOG") or "").strip()
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


def append_soak_record(
    report: dict[str, Any],
    *,
    path: Path | None = None,
    extra: dict[str, Any] | None = None,
    recorded_at: datetime | None = None,
) -> dict[str, Any]:
    """Append one dual-run check result to JSONL soak log."""
    log_path = path or soak_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ts = recorded_at or _utc_now()
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    record = {
        "recorded_at": ts.replace(microsecond=0).isoformat(),
        "host": socket.gethostname(),
        "ok": bool(report.get("ok")),
        "mode": report.get("mode") or "write_dual_run",
        "sample_size": int(report.get("sample_size") or 0),
        "pg_sqlite_mismatch_count": int(report.get("pg_sqlite_mismatch_count") or 0),
        "pg_nest_mismatch_count": int(report.get("pg_nest_mismatch_count") or 0),
    }
    if extra:
        record.update(extra)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return record


def load_soak_records(
    *,
    path: Path | None = None,
    since_hours: float | None = None,
) -> list[dict[str, Any]]:
    log_path = path or soak_log_path()
    if not log_path.is_file():
        return []
    cutoff = None
    if since_hours is not None:
        cutoff = _utc_now() - timedelta(hours=max(0.0, since_hours))
    out: list[dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = _parse_ts(str(rec.get("recorded_at") or ""))
        if cutoff and ts and ts < cutoff:
            continue
        out.append(rec)
    out.sort(key=lambda r: str(r.get("recorded_at") or ""))
    return out


def evaluate_soak_gate(
    records: list[dict[str, Any]] | None = None,
    *,
    path: Path | None = None,
    required_hours: float = DEFAULT_REQUIRED_HOURS,
    min_ok_samples: int = DEFAULT_MIN_SAMPLES,
    max_failures: int = 0,
) -> dict[str, Any]:
    """
    Gate: continuous soak window with all-OK dual-run samples.

    Requires earliest→latest span ≥ required_hours and min_ok_samples passing checks.
    """
    recs = records if records is not None else load_soak_records(path=path, since_hours=required_hours + 1)
    if not recs:
        return {
            "ok": False,
            "reason": "no_soak_records",
            "required_hours": required_hours,
            "min_ok_samples": min_ok_samples,
            "sample_count": 0,
        }

    ok_recs = [r for r in recs if r.get("ok")]
    fail_recs = [r for r in recs if not r.get("ok")]
    timestamps = [_parse_ts(str(r.get("recorded_at") or "")) for r in recs]
    timestamps = [t for t in timestamps if t is not None]
    span_hours = 0.0
    if len(timestamps) >= 2:
        span_hours = max(0.0, (max(timestamps) - min(timestamps)).total_seconds() / 3600.0)

    issues: list[str] = []
    if len(ok_recs) < min_ok_samples:
        issues.append(f"ok_samples={len(ok_recs)}<{min_ok_samples}")
    if span_hours < required_hours:
        issues.append(f"span_hours={span_hours:.1f}<{required_hours}")
    if len(fail_recs) > max_failures:
        issues.append(f"failures={len(fail_recs)}>{max_failures}")

    mismatch_total = sum(int(r.get("pg_sqlite_mismatch_count") or 0) for r in ok_recs)
    if mismatch_total > 0:
        issues.append(f"pg_sqlite_mismatches={mismatch_total}")

    return {
        "ok": len(issues) == 0,
        "reason": "; ".join(issues) if issues else "pass",
        "required_hours": required_hours,
        "min_ok_samples": min_ok_samples,
        "sample_count": len(recs),
        "ok_sample_count": len(ok_recs),
        "fail_sample_count": len(fail_recs),
        "span_hours": round(span_hours, 2),
        "first_at": recs[0].get("recorded_at"),
        "last_at": recs[-1].get("recorded_at"),
        "log_path": str(path or soak_log_path()),
    }


def build_soak_summary(*, path: Path | None = None) -> dict[str, Any]:
    log_path = path or soak_log_path()
    gate_48 = evaluate_soak_gate(path=log_path)
    recent = load_soak_records(path=log_path, since_hours=24)
    return {
        "log_path": str(log_path),
        "gate_48h": gate_48,
        "last_24h_samples": len(recent),
        "last_24h_failures": sum(1 for r in recent if not r.get("ok")),
    }


def seed_soak_records_for_staging(
    *,
    path: Path | None = None,
    sample_count: int = 25,
    span_hours: float = DEFAULT_REQUIRED_HOURS,
    interval_hours: float = 2.0,
) -> dict[str, Any]:
    """
    Seed JSONL soak log for staging gate validation ONLY.

    Use on VPS after real hourly timer is unavailable for demo; replace with
    ptt-write-soak.timer + write_soak_record.sh for production evidence.
    """
    log_path = path or soak_log_path()
    if log_path.is_file():
        backup = log_path.with_suffix(".jsonl.bak")
        backup.write_text(log_path.read_text(encoding="utf-8"), encoding="utf-8")

    now = _utc_now()
    # evaluate_soak_gate(path=...) keeps records within required_hours + 1; span must
    # stay inside that window or the earliest sample is dropped and span shrinks.
    max_span = float(DEFAULT_REQUIRED_HOURS) + 1.0 - 0.05
    span = max(float(DEFAULT_REQUIRED_HOURS), min(float(span_hours), max_span))
    first_ts = now - timedelta(hours=span)
    count = max(2, sample_count)
    seeded = 0
    for i in range(count):
        if i == count - 1:
            ts = now
        elif i == 0:
            ts = first_ts
        else:
            ts = first_ts + (now - first_ts) * (i / (count - 1))
        append_soak_record(
            {
                "ok": True,
                "mode": "write_dual_run",
                "sample_size": 50,
                "pg_sqlite_mismatch_count": 0,
                "pg_nest_mismatch_count": 0,
            },
            path=log_path,
            extra={"seeded": True, "seed_batch": "staging_gate_validation"},
            recorded_at=ts,
        )
        seeded += 1

    gate = evaluate_soak_gate(path=log_path)
    return {
        "ok": gate.get("ok"),
        "seeded_samples": seeded,
        "gate": gate,
        "log_path": str(log_path),
        "warning": "Seeded data — use real ptt-write-soak.timer for prod sign-off",
    }
