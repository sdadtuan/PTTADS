"""ZKTeco iClock PUSH protocol — MB20-VL, MB560-VL, ZMM series, v.v."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

# ZKTeco verify type → nhãn PTT
VERIFY_LABELS: dict[int, str] = {
    0: "password",
    1: "fingerprint",
    2: "card",
    3: "password",
    4: "card",
    15: "face",
    16: "face",
    17: "palm",
}

# status ATTLOG: 0=vào, 1=ra (chuẩn ZKTeco)
STATUS_TO_KIND: dict[int, str] = {
    0: "in",
    1: "out",
}


@dataclass
class ZkAttendanceLog:
    pin: str
    work_date: str
    time_hm: str
    kind: str
    verify: str
    raw_line: str


_RE_ATTLOG = re.compile(
    r"^(\d+)\s+(\d{4}-\d{2}-\d{2})[ T](\d{1,2}):(\d{2})(?::(\d{2}))?",
    re.MULTILINE,
)


def _verify_label(code: int) -> str:
    return VERIFY_LABELS.get(code, "device")


def _status_kind(status: int) -> str:
    return STATUS_TO_KIND.get(status, "auto")


def parse_attlog_body(body: str) -> list[ZkAttendanceLog]:
    """Parse nội dung POST /iclock/cdata (table=ATTLOG hoặc raw ATTLOG)."""
    logs: list[ZkAttendanceLog] = []
    if not body or not str(body).strip():
        return logs

    for raw_line in str(body).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        upper = line.upper()
        if upper.startswith("USER ") or upper.startswith("FP ") or upper.startswith("FACE "):
            continue

        parts = line.split("\t")
        if len(parts) < 2:
            parts = re.split(r"\s+", line, maxsplit=3)
        if len(parts) < 2:
            continue

        pin = str(parts[0]).strip()
        if not pin or not pin.isdigit():
            continue

        ts_raw = str(parts[1]).strip()
        m = re.match(r"^(\d{4}-\d{2}-\d{2})[ T](\d{1,2}):(\d{2})", ts_raw)
        if not m:
            continue
        wd = m.group(1)
        h, mi = int(m.group(2)), int(m.group(3))
        if h > 23 or mi > 59:
            continue
        hm = f"{h:02d}:{mi:02d}"

        status = 0
        verify_code = 0
        if len(parts) >= 3:
            try:
                status = int(str(parts[2]).strip())
            except ValueError:
                status = 0
        if len(parts) >= 4:
            try:
                verify_code = int(str(parts[3]).strip())
            except ValueError:
                verify_code = 0

        logs.append(
            ZkAttendanceLog(
                pin=pin,
                work_date=wd,
                time_hm=hm,
                kind=_status_kind(status),
                verify=_verify_label(verify_code),
                raw_line=line,
            )
        )

    if logs:
        return logs

    # Fallback: quét regex trên body lớn
    for m in _RE_ATTLOG.finditer(body):
        pin, wd, h, mi = m.group(1), m.group(2), int(m.group(3)), int(m.group(4))
        if h > 23 or mi > 59:
            continue
        logs.append(
            ZkAttendanceLog(
                pin=pin,
                work_date=wd,
                time_hm=f"{h:02d}:{mi:02d}",
                kind="auto",
                verify="device",
                raw_line=m.group(0),
            )
        )
    return logs


def iclock_get_response() -> str:
    """Phản hồi tối thiểu để máy tiếp tục push."""
    return "OK"


def iclock_options_response(device_sn: str = "") -> str:
    """Một số firmware hỏi OPTIONS qua GET /iclock/cdata."""
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    sn = device_sn or "PTT"
    return (
        f"GET OPTION FROM: {sn}\n"
        f"ATTLOGStamp={stamp}\n"
        f"OPERLOGStamp={stamp}\n"
        f"ErrorDelay=30\n"
        f"Delay=10\n"
        f"TransTimes=00:00;14:05\n"
        f"TransInterval=1\n"
        f"TransFlag=TransData AttLog\tOpLog\tAttPhoto\n"
        f"Realtime=1\n"
        f"Encrypt=0\n"
    )
