"""Trợ lý AI nội bộ cho CRM PTT — playbook CSKH, pipeline, ngữ cảnh case."""
from __future__ import annotations

import json
import os
import re
import sqlite3
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import Any

from crm_sales_pipeline import (
    SALES_PIPELINE_LABELS_VI,
    SALES_PIPELINE_STAGES,
    STAGE_SLA_HOURS,
    TERMINAL_STAGES,
)
from crm_admin_playbook import (
    format_admin_overview,
    format_payroll_export_guide,
    format_permission_guide,
)
from crm_workflow_playbook import CRM_LEAD_INTAKE_MASTER_FLOW, CRM_MARKETING_INGRESS_CHANNELS

DEFAULT_WELCOME = (
    "Xin chào! Tôi **làm việc trực tiếp** trong CRM PTT — xuất file, lấy số liệu, trả kết quả ngay.\n\n"
    "Ví dụ: *«Xuất bảng lương tháng 5 cho Nguyễn Văn A»* → file Excel/CSV trong khung chat.\n"
    "*«Thống kê pipeline»* → số liệu thời gian thực.\n"
    "Chỉ hỏi *«hướng dẫn…»* nếu bạn cần quy trình chi tiết."
)

DEFAULT_QUICK_REPLIES: tuple[str, ...] = (
    "Xuất bảng lương tháng này",
    "Xuất bảng lương tháng trước",
    "Thống kê pipeline hiện tại",
    "Case quá SLA hôm nay",
    "Hướng dẫn phân quyền CMS",
)

CRM_ASSISTANT_MODULES: tuple[dict[str, str], ...] = (
    {
        "id": "playbook",
        "label": "Playbook 6 bước",
        "prompt": "Tóm tắt playbook CRM 6 trụ khi lead marketing đổ về — từng bước, SLA, thao tác trên Bảng CSKH.",
    },
    {
        "id": "payroll",
        "label": "Xuất lương",
        "prompt": "Xuất bảng lương tháng này",
    },
    {
        "id": "pipeline",
        "label": "Pipeline",
        "prompt": "Thống kê pipeline hiện tại",
    },
)

CRM_KNOWLEDGE = """
Bối cảnh CRM PTT Advertising Solutions:
- Bảng CSKH: Kanban case, phễu pipeline, workspace nhân viên, playbook 6 trụ, trợ lý AI.
- Hub Marketing: chiến dịch, hợp đồng, nhắc việc gia hạn.
- Trang Khách hàng: hồ sơ 360°, timeline, báo cáo chăm sóc, vấn đề/issue.
- KPI nhân viên: chỉ tiêu theo kỳ, cảnh báo, biểu đồ đạt %.
- Chấm công & Lương (/crm/payroll): máy ZKTeco, import Excel (Mã PIN), tính lương giờ, phạt trễ,
  phụ cấp/thưởng cấp bậc, khóa kỳ, xuất Excel/CSV theo tháng/quý/khoảng — lọc theo staff_id hoặc q (tên/mã/PIN).
- Gửi bảng lương: hệ thống xuất file; HR gửi thủ công qua email/Zalo; NV xem portal /crm/payroll.
- Phân quyền: vai trò CMS (cms_roles) + chức vụ CRM (crm_positions); super_admin/cms_admin toàn quyền.
  Actions: view, edit, create, delete, export, configure. Tài liệu: docs/PHAN_QUYEN_HUONG_DAN.md.

Pipeline bán hàng (giai đoạn): Mới → Đang liên hệ → MQL → SQL → Báo giá → Chốt / Mất.
Mọi case phải có kênh (channel), priority, phụ trách (assigned_staff_id), timeline sự kiện.

Nguyên tắc vận hành:
- Lead hot: phản hồi ≤15 phút trong giờ hành chính.
- Không để lead overnight ngoài CRM.
- Tag chiến dịch/UTM để đo CPL và win rate theo nguồn.
- Báo giá ≤48h sau meeting; onboarding ≤3 ngày làm việc sau chốt.
- Cuối tháng: chốt chấm công → tính lương → khóa kỳ → xuất & gửi từng NV.
"""


def _norm(text: str) -> str:
    s = unicodedata.normalize("NFD", str(text or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _settings_flag(settings: dict[str, Any], key: str, *, default: bool = True) -> bool:
    raw = settings.get(key)
    if raw is None or raw == "":
        return default
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _build_context_summary_line(ctx: dict[str, Any]) -> str:
    parts: list[str] = []
    total = int(ctx.get("total_open") or 0)
    if total > 0:
        line = f"{total} case mở"
        overdue = int(ctx.get("sla_overdue") or 0)
        if overdue:
            line += f" · {overdue} quá SLA"
        parts.append(line)
    payroll = ctx.get("payroll")
    if isinstance(payroll, dict):
        py = payroll.get("year")
        pm = payroll.get("month")
        status = payroll.get("status_label") or payroll.get("status") or ""
        lines_cnt = int(payroll.get("lines_count") or 0)
        if py and pm:
            parts.append(f"Lương {pm:02d}/{py}: {lines_cnt} NV · {status}")
    return " · ".join(parts)


def _fetch_payroll_snapshot(
    conn: sqlite3.Connection,
    *,
    staff_id: int | None = None,
    year: int | None = None,
    month: int | None = None,
) -> dict[str, Any]:
    now = datetime.now()
    y = int(year or now.year)
    m = int(month or now.month)
    row = conn.execute(
        """
        SELECT p.id, p.year, p.month, p.status,
               COUNT(pl.id) AS lines_count,
               COALESCE(SUM(pl.net_salary_vnd), 0) AS total_net_vnd
        FROM crm_payroll p
        LEFT JOIN crm_payroll_line pl ON pl.payroll_id = p.id
        WHERE p.year = ? AND p.month = ?
        GROUP BY p.id
        """,
        (y, m),
    ).fetchone()
    status_labels = {"draft": "Nháp", "locked": "Đã khóa"}
    snap: dict[str, Any] = {"year": y, "month": m, "exists": False}
    if row:
        snap.update(
            {
                "exists": True,
                "payroll_id": int(row["id"]),
                "status": str(row["status"] or "draft"),
                "status_label": status_labels.get(str(row["status"] or "draft"), str(row["status"])),
                "lines_count": int(row["lines_count"] or 0),
                "total_net_vnd": int(row["total_net_vnd"] or 0),
            }
        )
    staff_list: list[dict[str, Any]] = []
    staff_rows = conn.execute(
        """
        SELECT id, name, internal_code, email, phone, attendance_pin
        FROM crm_staff
        WHERE COALESCE(active, 1) = 1
        ORDER BY name COLLATE NOCASE ASC
        LIMIT 200
        """
    ).fetchall()
    for sr in staff_rows:
        staff_list.append(
            {
                "id": int(sr["id"]),
                "name": str(sr["name"] or ""),
                "code": str(sr["internal_code"] or "").strip(),
                "email": str(sr["email"] or "").strip(),
                "phone": str(sr["phone"] or "").strip(),
                "attendance_pin": str(sr["attendance_pin"] or "").strip(),
            }
        )
    snap["staff_list"] = staff_list
    if staff_id is not None and snap.get("exists"):
        pl = conn.execute(
            """
            SELECT pl.net_salary_vnd, pl.days_present, pl.hours_worked_total,
                   s.name AS staff_name, s.internal_code AS staff_code
            FROM crm_payroll_line pl
            JOIN crm_payroll p ON p.id = pl.payroll_id
            JOIN crm_staff s ON s.id = pl.staff_id
            WHERE p.year = ? AND p.month = ? AND pl.staff_id = ?
            """,
            (y, m, int(staff_id)),
        ).fetchone()
        if pl:
            snap["staff_line"] = {
                "staff_id": int(staff_id),
                "staff_name": str(pl["staff_name"] or ""),
                "staff_code": str(pl["staff_code"] or ""),
                "net_salary_vnd": int(pl["net_salary_vnd"] or 0),
                "days_present": int(pl["days_present"] or 0),
                "hours_worked_total": float(pl["hours_worked_total"] or 0),
            }
    return snap


_NAME_FILLER_RE = re.compile(
    r"^(?:(?:la|là|anh|chi|chị|em|ban|bạn|cô|co|chu|thầy|thay|mr|ms|nv|"
    r"nhan\s*vien|nhân\s*viên|ten|tên)\s+)+",
    re.IGNORECASE,
)


def _clean_staff_hint(raw: str) -> str | None:
    hint = str(raw or "").strip().strip("\"'")
    hint = re.sub(r"\s*(?:tháng|thang|ky|kỳ)\s+\d+.*$", "", hint, flags=re.IGNORECASE).strip()
    hint = _NAME_FILLER_RE.sub("", hint).strip()
    hint = re.sub(r"^(?:ten|tên)\s+", "", hint, flags=re.IGNORECASE).strip()
    return hint if len(hint) >= 2 else None


def _name_search_tokens(hint: str) -> list[str]:
    """Tách từ khóa tên (ưu tiên từ cuối — thường là tên gọi)."""
    cleaned = _clean_staff_hint(hint) or str(hint or "").strip()
    parts = [p for p in re.split(r"\s+", cleaned) if len(p) >= 2]
    if not parts:
        return [cleaned] if len(cleaned) >= 2 else []
    ordered: list[str] = []
    seen: set[str] = set()
    for p in list(reversed(parts)) + sorted(parts, key=len, reverse=True):
        key = p.lower()
        if key not in seen:
            seen.add(key)
            ordered.append(p)
    return ordered


def _find_staff_by_name_hint(hint: str, staff_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matches = _find_staff_matches_by_query(hint, staff_list)
    if matches:
        return matches
    for token in _name_search_tokens(hint):
        matches = _find_staff_matches_by_query(token, staff_list)
        if matches:
            return matches
    return []


def _staff_haystack(staff: dict[str, Any]) -> str:
    return _norm(
        " ".join(
            [
                str(staff.get("name") or ""),
                str(staff.get("code") or ""),
                str(staff.get("attendance_pin") or ""),
            ]
        )
    )


def _find_staff_matches_by_query(query: str, staff_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cùng logic lọc như trang Chấm công → Xuất file (tên / mã NV / PIN)."""
    q = _norm(query)
    if not q:
        return list(staff_list)
    return [s for s in staff_list if q in _staff_haystack(s)]


def _find_staff_by_code(query: str, staff_list: list[dict[str, Any]], *, exact: bool = True) -> list[dict[str, Any]]:
    qc = _norm(query).replace(" ", "")
    if not qc:
        return []
    matches: list[dict[str, Any]] = []
    for s in staff_list:
        sc = _norm(str(s.get("code") or "")).replace(" ", "")
        if not sc:
            continue
        if exact:
            if sc == qc:
                matches.append(s)
        elif qc in sc:
            matches.append(s)
    return matches


def _find_staff_by_pin(query: str, staff_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    qp = _norm(query).replace(" ", "")
    if not qp:
        return []
    return [
        s
        for s in staff_list
        if _norm(str(s.get("attendance_pin") or "")).replace(" ", "") == qp
    ]


def _match_staff_by_cand(cand: "_StaffCand", staff_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if cand.kind in ("explicit_code", "embed_code"):
        exact = cand.kind == "explicit_code"
        return _find_staff_by_code(cand.value, staff_list, exact=exact)
    if cand.kind in ("explicit_pin", "embed_pin"):
        return _find_staff_by_pin(cand.value, staff_list)
    return _find_staff_by_name_hint(cand.value, staff_list)


class _StaffCand:
    __slots__ = ("value", "kind")

    def __init__(self, value: str, kind: str) -> None:
        self.value = value
        self.kind = kind


def _staff_search_candidates(question: str, staff_list: list[dict[str, Any]]) -> list[_StaffCand]:
    """Các chuỗi tìm kiếm NV theo thứ tự ưu tiên (explicit trước, fuzzy sau)."""
    raw = str(question or "").strip()
    explicit: list[_StaffCand] = []
    fuzzy: list[_StaffCand] = []
    seen: set[str] = set()

    def add(val: str | None, kind: str, *, force_explicit: bool = False) -> None:
        v = str(val or "").strip()
        if len(v) < 2:
            return
        if kind == "token" and v.isdigit() and len(v) < 4:
            return
        key = f"{kind}:{v.lower()}"
        if key in seen:
            return
        seen.add(key)
        bucket = explicit if force_explicit or kind.startswith("explicit_") else fuzzy
        bucket.append(_StaffCand(v, kind))

    code_patterns = (
        r"(?:ma|mã)\s*(?:nv|nhan\s*vi[eê]n|noi\s*bo|nội\s*bộ)?\s*[:\-]?\s*([\w][\w\-./]*)",
    )
    pin_patterns = (
        r"(?:pin|mã\s*pin|ma\s*pin|mã\s*chấm\s*công|ma\s*cham\s*cong)\s*[:\-]?\s*([\w\-./]+)",
    )
    for pat in code_patterns:
        m = re.search(pat, raw, re.IGNORECASE)
        if m:
            add(_clean_staff_hint(m.group(1)), "explicit_code", force_explicit=True)
    for pat in pin_patterns:
        m = re.search(pat, raw, re.IGNORECASE)
        if m:
            add(_clean_staff_hint(m.group(1)), "explicit_pin", force_explicit=True)

    name_patterns = (
        r"(?:ten|tên)\s+(?:la|là\s+)?(.+?)(?:\s*(?:tháng|thang|ky|kỳ|,|$)|$)",
        r"(?:nhan\s*vi[eê]n|nhan vien)\s+(?:(?:ten|tên)\s+(?:la|là\s+)?)?(.+?)(?:\s*(?:tháng|thang|ky|kỳ)|$)",
        r"(?:cho|for)\s+(?:(?:ten|tên)\s+(?:la|là\s+)?(.+?)|(?:nhan\s*vi[eê]n|nhan vien)\s+(?:(?:ten|tên)\s+(?:la|là\s+)?)?(.+?))(?:\s*(?:tháng|thang)|$)",
    )
    for pat in name_patterns:
        m = re.search(pat, raw, re.IGNORECASE)
        if m:
            captured = next((g for g in m.groups() if g), "")
            add(_clean_staff_hint(captured), "explicit_name", force_explicit=True)

    q_low = raw.lower()
    q_norm = _norm(question)
    for s in sorted(staff_list, key=lambda x: len(str(x.get("name") or "")), reverse=True):
        name = str(s.get("name") or "").strip()
        if len(name) >= 2 and (name.lower() in q_low or _norm(name) in q_norm):
            add(name, "embed_name")
        for part in name.split():
            if len(part) >= 2 and _norm(part) in q_norm:
                add(part, "embed_name")
    for s in sorted(staff_list, key=lambda x: len(str(x.get("code") or "")), reverse=True):
        code = str(s.get("code") or "").strip()
        if len(code) >= 3 and (_norm(code) in q_norm or code.lower() in q_low):
            add(code, "embed_code")
        pin = str(s.get("attendance_pin") or "").strip()
        if len(pin) >= 4 and re.search(rf"(?<!\w){re.escape(_norm(pin))}(?!\w)", q_norm):
            add(pin, "embed_pin")

    has_strict_explicit = any(c.kind in ("explicit_code", "explicit_pin") for c in explicit)
    if not has_strict_explicit:
        noise = q_norm
        noise = re.sub(r"thang\s+\d{1,2}(?:\s+\d{4})?", " ", noise)
        noise = re.sub(r"\bt\d{1,2}\b", " ", noise)
        stop = frozenset(
            {
                "xuat", "file", "bang", "luong", "payroll", "thang", "ky", "cho", "nhan", "vien",
                "ten", "ma", "nv", "excel", "csv", "tai", "lay", "gui", "goi", "theo", "tung",
                "nhanvien", "this", "month", "nam", "pin", "noi", "bo", "internal", "code", "la",
            }
        )
        tokens = [t for t in noise.split() if t and t not in stop and len(t) >= 2]
        if len(tokens) >= 2:
            add(" ".join(tokens[-3:]), "token")
        if tokens:
            add(tokens[-1], "token")

    return explicit + fuzzy


def fetch_staff_list_for_search(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, name, internal_code, attendance_pin
        FROM crm_staff
        WHERE COALESCE(active, 1) = 1
        ORDER BY name COLLATE NOCASE ASC
        """
    ).fetchall()
    out: list[dict[str, Any]] = []
    for sr in rows:
        out.append(
            {
                "id": int(sr["id"]),
                "name": str(sr["name"] or ""),
                "code": str(sr["internal_code"] or "").strip(),
                "attendance_pin": str(sr["attendance_pin"] or "").strip(),
            }
        )
    return out


def find_payroll_staff_ids_by_query(conn: sqlite3.Connection, query: str) -> list[int]:
    """Lọc staff_id khớp tên / mã NV / PIN — dùng chung cho export API và trợ lý."""
    staff = fetch_staff_list_for_search(conn)
    qn = _norm(query)
    if not qn:
        return [int(s["id"]) for s in staff]
    by_code = _find_staff_by_code(query, staff, exact=True)
    if by_code:
        return [int(s["id"]) for s in by_code]
    by_pin = _find_staff_by_pin(query, staff)
    if by_pin:
        return [int(s["id"]) for s in by_pin]
    return [int(s["id"]) for s in _find_staff_by_name_hint(query, staff)]


def _extract_staff_name_hint(question: str, staff_list: list[dict[str, Any]] | None = None) -> str | None:
    cands = _staff_search_candidates(question, staff_list or [])
    return cands[0].value if cands else None


def _staff_matches_name_hint(staff: dict[str, Any], hint: str) -> bool:
    return staff in _find_staff_matches_by_query(hint, [staff])


def _db_like_staff_query(query: str, matches: list[dict[str, Any]]) -> str:
    """Chuỗi `q` cho API export — ưu tiên có dấu từ tên/mã NV thật (SQLite LIKE)."""
    qn = _norm(query)
    if not qn:
        return str(query or "").strip()
    for m in matches:
        name = str(m.get("name") or "")
        for part in name.split():
            if qn in _norm(part):
                return part
        if qn in _norm(name):
            return name
        code = str(m.get("code") or "").strip()
        if code and qn in _norm(code):
            return code
        pin = str(m.get("attendance_pin") or "").strip()
        if pin and qn == _norm(pin):
            return pin
    return str(query or "").strip()


def _resolve_payroll_staff_filter(
    question: str,
    staff_list: list[dict[str, Any]],
    *,
    portal_staff_id: int | None = None,
) -> tuple[int | None, str | None, str, str | None]:
    """
    Trả về (staff_id, staff_q, label, error).
    Một NV khớp → staff_id; nhiều NV khớp → staff_q; không khớp explicit → error.
    """
    if portal_staff_id is not None:
        return portal_staff_id, None, "của bạn", None

    cands = _staff_search_candidates(question, staff_list)
    strict = [c for c in cands if c.kind in ("explicit_code", "explicit_pin")]
    searchable = [c for c in cands if c.kind not in ("explicit_code", "explicit_pin")]

    def pack_single(s: dict[str, Any], fallback: str) -> tuple[int | None, str | None, str, str | None]:
        code = str(s.get("code") or "").strip()
        label = str(s.get("name") or fallback)
        if code:
            label = f"{label} ({code})"
        return int(s["id"]), None, label, None

    def try_cand(cand: _StaffCand) -> tuple[int | None, str | None, str, str | None] | None:
        matches = _match_staff_by_cand(cand, staff_list)
        if len(matches) == 1:
            return pack_single(matches[0], cand.value)
        if len(matches) > 1:
            sq = _db_like_staff_query(cand.value, matches)
            return None, sq, sq, None
        return None

    for cand in strict:
        hit = try_cand(cand)
        if hit:
            return hit
    if strict:
        hint = strict[0].value
        return None, None, hint, f"Không tìm thấy nhân viên «{hint}». Kiểm tra Mã NV / Tên / PIN."

    for cand in searchable:
        hit = try_cand(cand)
        if hit:
            return hit

    name_cands = [c for c in cands if c.kind == "explicit_name"]
    for cand in name_cands:
        for token in _name_search_tokens(cand.value):
            matches = _find_staff_matches_by_query(token, staff_list)
            if len(matches) == 1:
                return pack_single(matches[0], token)
            if len(matches) > 1:
                sq = _db_like_staff_query(token, matches)
                return None, sq, sq, None

    if name_cands:
        hint = _clean_staff_hint(name_cands[0].value) or name_cands[0].value
        return None, None, hint, f"Không tìm thấy nhân viên «{hint}». Kiểm tra Mã NV / Tên / PIN."

    return None, None, "tất cả nhân viên", None


def _match_staff_from_question(question: str, staff_list: list[dict[str, Any]]) -> dict[str, Any] | None:
    for cand in _staff_search_candidates(question, staff_list):
        matches = _match_staff_by_cand(cand, staff_list)
        if len(matches) == 1:
            return matches[0]
    return None


def parse_payroll_month_from_text(text: str) -> tuple[int, int]:
    """Suy kỳ lương từ câu hỏi — mặc định tháng hiện tại."""
    now = datetime.now()
    q = _norm(text)
    m = re.search(r"thang\s*(\d{1,2})(?:\s*(\d{4}))?", q)
    if m:
        month = int(m.group(1))
        year = int(m.group(2)) if m.group(2) else now.year
        if 1 <= month <= 12 and 2000 <= year <= 2100:
            return year, month
    m = re.search(r"(\d{1,2})\s*/\s*(\d{4})", q)
    if m:
        month, year = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12 and 2000 <= year <= 2100:
            return year, month
    m = re.search(r"\bt(\d{1,2})\b", q)
    if m:
        month = int(m.group(1))
        if 1 <= month <= 12:
            return now.year, month
    if "thang truoc" in q or "ky truoc" in q:
        if now.month == 1:
            return now.year - 1, 12
        return now.year, now.month - 1
    return now.year, now.month


def _is_guide_only_request(text: str) -> bool:
    """User chỉ muốn hướng dẫn, không yêu cầu thực thi."""
    q = _norm(text)
    guide_kw = (
        "huong dan",
        "cach lam",
        "lam sao",
        "how to",
        "checklist",
        "quy trinh",
        "playbook",
        "giai thich",
        "la gi",
    )
    action_kw = ("xuat", "tai", "lay", "gui", "goi", "file", "excel", "csv", "thong ke", "bao cao")
    if any(g in q for g in guide_kw):
        return not any(a in q for a in action_kw)
    return False


def wants_payroll_export(text: str) -> bool:
    """Yêu cầu xuất / nhận file bảng lương — thực thi, không chỉ hỏi cách làm."""
    if _is_guide_only_request(text):
        return False
    q = _norm(text)
    if any(k in q for k in ("bang luong", "payroll", "tep luong", "file luong")):
        return True
    if "luong" in q and any(
        k in q for k in ("xuat", "tai", "lay", "gui", "goi", "file", "excel", "csv", "bang", "ky")
    ):
        return True
    return False


# Giữ tên cũ cho tương thích nội bộ
wants_payroll_file = wants_payroll_export


def wants_daily_work_report_template(text: str) -> bool:
    """Yêu cầu tải mẫu báo cáo công việc hàng ngày."""
    if _is_guide_only_request(text):
        return False
    q = _norm(text)
    if "bao cao cong viec" in q or "bao cao cv" in q:
        return any(k in q for k in ("mau", "template", "file", "excel", "tai", "xuat", "lay"))
    if "cong viec hang ngay" in q or "bc cong viec" in q:
        return any(k in q for k in ("mau", "template", "file", "excel", "tai", "xuat"))
    if "mau bao cao" in q and any(k in q for k in ("ngay", "hang ngay", "cong viec", "nv", "nhan vien")):
        return True
    return False


def wants_daily_work_report_page(text: str) -> bool:
    """Yêu cầu nhập báo cáo hoặc xem lịch sử trên hệ thống (không chỉ tải Excel)."""
    if _is_guide_only_request(text):
        return False
    q = _norm(text)
    if not any(
        k in q
        for k in (
            "bao cao cong viec",
            "bao cao cv",
            "bc cong viec",
            "cong viec hang ngay",
            "bao cao ngay",
            "bc ngay",
        )
    ):
        return False
    if wants_daily_work_report_template(text):
        return False
    return any(
        k in q
        for k in (
            "nhap",
            "luu",
            "nop",
            "tao",
            "dien",
            "ghi",
            "quan ly",
            "lich su",
            "xem lai",
            "he thong",
            "trang",
            "portal",
        )
    )


def build_daily_work_report_file_attachments(
    question: str,
    *,
    portal_staff_id: int | None = None,
) -> list[dict[str, str]]:
    if not wants_daily_work_report_template(question):
        return []
    y, m = parse_payroll_month_from_text(question)
    params: dict[str, Any] = {"year": y, "month": m}
    if portal_staff_id is not None:
        params["staff_id"] = portal_staff_id
    url = "/api/crm/staff/daily-work-report-template?" + urllib.parse.urlencode(params)
    period = f"{m:02d}/{y}"
    return [
        {
            "url": url,
            "label": f"Mẫu BC công việc ngày — {period}",
            "format": "xlsx",
            "filename": f"mau-bao-cao-cong-viec-{period.replace('/', '-')}.xlsx",
        }
    ]


def _payroll_rows_exist(
    conn: sqlite3.Connection,
    *,
    year: int,
    month: int,
    staff_id: int | None = None,
    staff_q: str | None = None,
) -> bool:
    params: list[Any] = [year, year, month, year, year, month]
    extra = ""
    if staff_id is not None:
        extra = " AND pl.staff_id = ?"
        params.append(int(staff_id))
    elif staff_q:
        staff_ids = find_payroll_staff_ids_by_query(conn, staff_q)
        if not staff_ids:
            return False
        placeholders = ",".join("?" * len(staff_ids))
        extra = f" AND pl.staff_id IN ({placeholders})"
        params.extend(staff_ids)
    row = conn.execute(
        f"""
        SELECT COUNT(*) FROM crm_payroll_line pl
        JOIN crm_payroll p ON p.id = pl.payroll_id
        JOIN crm_staff s ON s.id = pl.staff_id
        WHERE (p.year > ? OR (p.year = ? AND p.month >= ?))
          AND (p.year < ? OR (p.year = ? AND p.month <= ?))
          {extra}
        """,
        params,
    ).fetchone()
    return int(row[0] or 0) > 0


def build_payroll_file_attachments(
    question: str,
    context: dict[str, Any],
    conn: sqlite3.Connection,
    *,
    portal_staff_id: int | None = None,
) -> list[dict[str, str]]:
    """Tạo link tải Excel/CSV bảng lương gắn vào phản hồi chat."""
    if not wants_payroll_export(question):
        return []

    year, month = parse_payroll_month_from_text(question)
    payroll = context.get("payroll") if isinstance(context.get("payroll"), dict) else {}
    staff_list = payroll.get("staff_list") if isinstance(payroll, dict) else []

    staff_id, staff_q, staff_label, staff_err = _resolve_payroll_staff_filter(
        question, staff_list or [], portal_staff_id=portal_staff_id
    )
    if staff_err:
        return []

    if staff_id is not None:
        if not _payroll_rows_exist(conn, year=year, month=month, staff_id=staff_id):
            return []
    elif staff_q:
        if not _payroll_rows_exist(conn, year=year, month=month, staff_q=staff_q):
            return []
    elif not _payroll_rows_exist(conn, year=year, month=month):
        return []

    base_params: dict[str, Any] = {
        "period": "month",
        "year": year,
        "month": month,
    }
    if staff_id is not None:
        base_params["staff_id"] = staff_id
    elif staff_q:
        base_params["q"] = staff_q.strip()

    period_label = f"{month:02d}/{year}"
    files: list[dict[str, str]] = []
    for fmt, ext in (("xlsx", "xlsx"), ("csv", "csv")):
        params = {**base_params, "format": fmt}
        url = "/api/crm/payroll/export?" + urllib.parse.urlencode(params)
        safe_name = re.sub(r"[^\w\-]+", "_", staff_label)[:40].strip("_") or "bang-luong"
        files.append(
            {
                "url": url,
                "label": f"Excel {period_label} — {staff_label}" if fmt == "xlsx" else f"CSV {period_label}",
                "format": fmt,
                "filename": f"bang-luong-{period_label.replace('/', '-')}-{safe_name}.{ext}",
            }
        )
    return files


def _payroll_action_message(
    question: str,
    context: dict[str, Any],
    *,
    portal_staff_id: int | None = None,
) -> str:
    year, month = parse_payroll_month_from_text(question)
    payroll = context.get("payroll") if isinstance(context.get("payroll"), dict) else {}
    staff_list = payroll.get("staff_list") if isinstance(payroll, dict) else []
    _sid, _sq, label, _err = _resolve_payroll_staff_filter(
        question, staff_list or [], portal_staff_id=portal_staff_id
    )

    extra = ""
    sl = payroll.get("staff_line") if isinstance(payroll, dict) else None
    if isinstance(sl, dict) and sl.get("net_salary_vnd") is not None and _sid is not None:
        extra = f" · Thực lĩnh **{int(sl['net_salary_vnd']):,}** VND"

    if _sq and not _sid:
        return f"**Bảng lương {month:02d}/{year}** — NV tên **{label}** (mọi người khớp tên)."

    return f"**Bảng lương {month:02d}/{year}** — {label}{extra}."


def build_crm_assistant_config(
    settings: dict[str, Any] | None = None,
    *,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    s = settings or {}
    welcome = str(s.get("crm_assistant_welcome") or "").strip() or DEFAULT_WELCOME
    quick_raw = str(s.get("crm_assistant_quick_json") or "").strip()
    quick: list[str] = list(DEFAULT_QUICK_REPLIES)
    if quick_raw:
        try:
            parsed = json.loads(quick_raw)
            if isinstance(parsed, list) and parsed:
                quick = [str(x).strip() for x in parsed if str(x).strip()][:8]
        except ValueError:
            pass
    has_ai = bool(os.environ.get("OPENAI_API_KEY", "").strip())
    ctx = context or {}
    return {
        "enabled": _settings_flag(s, "crm_assistant_enabled", default=True),
        "title": str(s.get("crm_assistant_title") or "Trợ lý CRM").strip(),
        "subtitle": str(
            s.get("crm_assistant_subtitle") or "CSKH · Quản trị · Lương · Phân quyền"
        ).strip(),
        "welcome": welcome,
        "placeholder": str(
            s.get("crm_assistant_placeholder")
            or "Hỏi CSKH, xuất/gửi lương, phân quyền, checklist quản trị…"
        ).strip(),
        "quick_replies": quick[:10],
        "modules": [dict(m) for m in CRM_ASSISTANT_MODULES],
        "context_summary": _build_context_summary_line(ctx),
        "context": ctx,
        "ai_enabled": has_ai,
        "ai_note": (
            "Đang dùng OpenAI (OPENAI_API_KEY)."
            if has_ai
            else "Chưa có OPENAI_API_KEY — trả lời theo playbook & dữ liệu CRM."
        ),
    }


def fetch_crm_context(
    conn: sqlite3.Connection,
    *,
    staff_id: int | None = None,
    case_id: int | None = None,
) -> dict[str, Any]:
    """Thống kê pipeline và (tuỳ chọn) tóm tắt một case."""
    where_parts = ["COALESCE(c.pipeline_stage, 'moi') NOT IN ('chot', 'mat')"]
    params: list[Any] = []
    if staff_id is not None:
        where_parts.append("c.assigned_staff_id = ?")
        params.append(int(staff_id))
    where_sql = " AND ".join(where_parts)

    stage_rows = conn.execute(
        f"""
        SELECT COALESCE(c.pipeline_stage, 'moi') AS stage, COUNT(*) AS cnt
        FROM crm_cases c
        WHERE {where_sql}
        GROUP BY stage
        """,
        params,
    ).fetchall()
    by_stage: dict[str, int] = {st: 0 for st in SALES_PIPELINE_STAGES}
    total_open = 0
    for r in stage_rows:
        st = str(r["stage"] or "moi")
        cnt = int(r["cnt"] or 0)
        by_stage[st] = cnt
        total_open += cnt

    unassigned = int(
        conn.execute(
            """
            SELECT COUNT(*) FROM crm_cases c
            WHERE COALESCE(c.pipeline_stage, 'moi') NOT IN ('chot', 'mat')
              AND (c.assigned_staff_id IS NULL OR c.assigned_staff_id = 0)
            """
        ).fetchone()[0]
        or 0
    )

    now = datetime.now()
    sla_overdue = 0
    overdue_rows = conn.execute(
        f"""
        SELECT c.id, COALESCE(c.pipeline_stage, 'moi') AS stage, c.updated_at
        FROM crm_cases c
        WHERE {where_sql}
        """,
        params,
    ).fetchall()
    for r in overdue_rows:
        st = str(r["stage"] or "moi")
        if st in TERMINAL_STAGES:
            continue
        sla_h = STAGE_SLA_HOURS.get(st, 0)
        if sla_h <= 0:
            continue
        updated_raw = str(r["updated_at"] or "").strip()
        try:
            updated = datetime.strptime(updated_raw[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        if updated + timedelta(hours=sla_h) < now:
            sla_overdue += 1

    ctx: dict[str, Any] = {
        "total_open": total_open,
        "unassigned": unassigned,
        "sla_overdue": sla_overdue,
        "by_stage": [
            {
                "stage": st,
                "label": SALES_PIPELINE_LABELS_VI.get(st, st),
                "count": by_stage.get(st, 0),
            }
            for st in SALES_PIPELINE_STAGES
            if st not in TERMINAL_STAGES
        ],
        "staff_scoped": staff_id is not None,
    }

    if case_id:
        row = conn.execute(
            """
            SELECT c.id, c.title, c.description, c.channel, c.priority, c.status,
                   COALESCE(c.pipeline_stage, 'moi') AS pipeline_stage,
                   c.updated_at, c.assigned_staff_id,
                   cu.name AS customer_name,
                   st.name AS staff_name
            FROM crm_cases c
            JOIN crm_customers cu ON cu.id = c.customer_id
            LEFT JOIN crm_staff st ON st.id = c.assigned_staff_id
            WHERE c.id = ?
            """,
            (int(case_id),),
        ).fetchone()
        if row:
            ctx["case"] = {
                "id": int(row["id"]),
                "title": str(row["title"] or ""),
                "pipeline_stage": str(row["pipeline_stage"] or "moi"),
                "pipeline_label": SALES_PIPELINE_LABELS_VI.get(
                    str(row["pipeline_stage"] or "moi"), str(row["pipeline_stage"] or "moi")
                ),
                "priority": str(row["priority"] or ""),
                "status": str(row["status"] or ""),
                "channel": str(row["channel"] or ""),
                "customer_name": str(row["customer_name"] or ""),
                "staff_name": str(row["staff_name"] or ""),
                "updated_at": str(row["updated_at"] or ""),
                "description_excerpt": str(row["description"] or "")[:400],
            }
    if staff_id is None:
        ctx["payroll"] = _fetch_payroll_snapshot(conn)
    elif staff_id is not None:
        ctx["payroll"] = _fetch_payroll_snapshot(conn, staff_id=staff_id)
    return ctx


def _format_playbook_summary() -> str:
    lines = ["**Playbook CRM — 6 trụ khi lead marketing đổ về**\n"]
    for step in CRM_LEAD_INTAKE_MASTER_FLOW:
        lines.append(f"**{step.get('phase', '')} — {step.get('title', '')}**")
        lines.append(f"_Vị trí CRM:_ {step.get('crm_where', '')} · _SLA:_ {step.get('sla', '')}")
        for act in step.get("actions") or []:
            lines.append(f"- {act}")
        lines.append("")
    return "\n".join(lines).strip()


def _format_pipeline_sla() -> str:
    lines = ["**Pipeline bán hàng & SLA (giờ)**\n", "| Giai đoạn | SLA |", "|---|---|"]
    for st in SALES_PIPELINE_STAGES:
        if st in TERMINAL_STAGES:
            continue
        label = SALES_PIPELINE_LABELS_VI.get(st, st)
        sla = STAGE_SLA_HOURS.get(st, 0)
        lines.append(f"| {label} | {sla}h |" if sla else f"| {label} | — |")
    lines.append(
        "\nLead quá SLA: ưu tiên liên hệ lại, cập nhật timeline, "
        "kéo giai đoạn phù hợp hoặc nurture nếu chưa qualify."
    )
    return "\n".join(lines)


def _format_channel_intake(channel_hint: str) -> str | None:
    q = _norm(channel_hint)
    for ch in CRM_MARKETING_INGRESS_CHANNELS:
        keys = (
            _norm(ch.get("id", "")),
            _norm(ch.get("label", "")),
            _norm(ch.get("crm_channel_label", "")),
        )
        if any(k and k in q for k in keys):
            lines = [
                f"**{ch.get('icon', '')} {ch.get('label', '')}**\n",
                f"_Phát hiện:_ {ch.get('detect', '')}",
                f"_SLA liên hệ:_ {ch.get('sla_contact', '')}",
                f"_Priority gợi ý:_ {ch.get('priority_hint', '')}\n",
                "**Checklist T+0:**",
            ]
            for item in ch.get("t0_checklist") or []:
                lines.append(f"- {item}")
            return "\n".join(lines)
    return None


def _format_context_snapshot(context: dict[str, Any] | None) -> str | None:
    if not context:
        return None
    parts: list[str] = []
    total = int(context.get("total_open") or 0)
    if total > 0:
        parts.append(f"**Pipeline hiện tại:** {total} case đang mở")
        overdue = int(context.get("sla_overdue") or 0)
        if overdue:
            parts.append(f"⚠ **{overdue}** case quá SLA — ưu tiên xử lý trước.")
        unassigned = int(context.get("unassigned") or 0)
        if unassigned and not context.get("staff_scoped"):
            parts.append(f"**{unassigned}** case chưa gán phụ trách.")
        by_stage = context.get("by_stage") or []
        nonzero = [f"{x['label']}: {x['count']}" for x in by_stage if int(x.get("count") or 0) > 0]
        if nonzero:
            parts.append("Phân bổ: " + " · ".join(nonzero))
    elif not context.get("case"):
        parts.append(
            "**Pipeline hiện tại:** không có case đang mở"
            + (" (theo phạm vi của bạn)." if context.get("staff_scoped") else ".")
        )
    case = context.get("case")
    if isinstance(case, dict):
        parts.append(
            f"\n**Case #{case.get('id')}** — {case.get('title', '')}\n"
            f"Khách: {case.get('customer_name', '')} · Giai đoạn: **{case.get('pipeline_label', '')}** · "
            f"Priority: {case.get('priority', '')}"
        )
    payroll = context.get("payroll")
    if isinstance(payroll, dict) and payroll.get("exists"):
        py = int(payroll.get("year") or 0)
        pm = int(payroll.get("month") or 0)
        parts.append(
            f"\n**Lương {pm:02d}/{py}:** {payroll.get('lines_count', 0)} NV · "
            f"{payroll.get('status_label', payroll.get('status', ''))}"
        )
        sl = payroll.get("staff_line")
        if isinstance(sl, dict):
            parts.append(
                f"NV **{sl.get('staff_name', '')}** — thực lĩnh {sl.get('net_salary_vnd', 0):,} VND · "
                f"{sl.get('days_present', 0)} ngày công"
            )
    return "\n".join(parts)


def _rule_based_reply(question: str, context: dict[str, Any] | None = None) -> str | None:
    q = _norm(question)
    if not q:
        return None

    # Trả số liệu trực tiếp — không hướng dẫn UI
    if any(
        k in q
        for k in ("thong ke", "pipeline hien tai", "case dang mo", "bao cao pipeline", "case qua sla")
    ):
        snap = _format_context_snapshot(context)
        return snap or "Chưa có case đang mở trong phạm vi bạn xem."

    # Xuất lương — xử lý ở build_crm_assistant_response (đính kèm file)
    if wants_payroll_export(question):
        return None

    # Playbook — user hỏi rõ nội dung quy trình
    if any(k in q for k in ("playbook", "6 buoc", "6 tru")):
        return _format_playbook_summary()

    # Chỉ trả hướng dẫn dài khi user hỏi «hướng dẫn / cách»
    if not _is_guide_only_request(question):
        return None

    if any(k in q for k in ("playbook", "6 buoc", "6 tru", "quy trinh crm", "lead moi", "lead marketing")):
        return _format_playbook_summary()

    if any(k in q for k in ("pipeline", "sla", "qua han", "kanban", "giai doan")):
        base = _format_pipeline_sla()
        snap = _format_context_snapshot(context)
        return f"{base}\n\n{snap}" if snap else base

    if any(k in q for k in ("form", "landing", "ads", "facebook", "google", "zalo", "mxh", "kenh")):
        ch = _format_channel_intake(question)
        if ch:
            return ch

    if any(k in q for k in ("bang luong", "payroll", "luong", "xuat luong")):
        payroll = (context or {}).get("payroll") if isinstance((context or {}).get("payroll"), dict) else {}
        staff_list = payroll.get("staff_list") if isinstance(payroll, dict) else []
        matched_staff = _match_staff_from_question(question, staff_list or [])
        hint = matched_staff.get("name", "") if matched_staff else ""
        sid = matched_staff.get("id") if matched_staff else None
        return format_payroll_export_guide(staff_hint=hint, staff_id=sid)

    if any(k in q for k in ("mql", "sql", "qualify", "phan loai", "bao gia", "chot", "timeline", "nuoi duong")):
        return _rule_based_reply_coaching(question, context)

    if any(k in q for k in ("quan tri", "admin can", "checklist", "hang thang", "van hanh", "toan bo")):
        return format_admin_overview()

    if any(k in q for k in ("phan quyen", "quyen cms", "chuc vu", "vai tro", "permissions", "ma tran")):
        return format_permission_guide()

    return None


def _rule_based_reply_coaching(question: str, context: dict[str, Any] | None) -> str | None:
    """Playbook CSKH — chỉ dùng khi user yêu cầu hướng dẫn."""
    q = _norm(question)
    if any(k in q for k in ("mql", "sql", "qualify", "phan loai")):
        return (
            "**Qualify MQL → SQL**\n\n"
            "1. Nhu cầu + ngân sách rõ → **MQL**.\n"
            "2. Hẹn demo → **SQL** + reminder.\n"
            "3. Chưa đủ → nurture D3/D7."
        )
    if any(k in q for k in ("bao gia", "chot", "proposal", "deal")):
        return "**Chốt deal:** báo giá ≤48h sau meeting → hợp đồng Hub trong 24h → **Chốt**."
    if any(k in q for k in ("timeline", "bao cao cham soc", "care report", "cskh")):
        return "**CSKH:** ghi timeline mỗi touch; báo cáo chăm sóc trên case."
    if any(k in q for k in ("nuoi duong", "nurture", "d0", "d7")):
        return "**Nurture:** D0 gọi/Zalo · D1 gọi lại · D3 email · D7 qualify."
    case = (context or {}).get("case")
    if isinstance(case, dict) and any(k in q for k in ("buoc tiep", "lam gi", "goi y", "case nay")):
        stage = str(case.get("pipeline_stage") or "moi")
        label = case.get("pipeline_label") or stage
        return f"**Case #{case.get('id')}** ({label}) — khách {case.get('customer_name', '')}. Cập nhật timeline và giai đoạn pipeline."
    return None


def _context_block(context: dict[str, Any] | None) -> str:
    if not context:
        return ""
    parts: list[str] = []
    snap = _format_context_snapshot(context)
    if snap:
        parts.append(f"Dữ liệu CRM thời gian thực:\n{snap}")
    payroll = context.get("payroll")
    if isinstance(payroll, dict) and payroll.get("staff_list") and not context.get("staff_scoped"):
        names = [
            f"{s.get('name')} (id={s.get('id')})"
            for s in (payroll.get("staff_list") or [])[:15]
            if s.get("name")
        ]
        if names:
            parts.append("Nhân viên active (mẫu): " + "; ".join(names))
    return "\n\n" + "\n\n".join(parts) if parts else ""


def _openai_reply(
    question: str,
    history: list[dict[str, Any]],
    settings: dict[str, Any],
    context: dict[str, Any] | None,
    api_key: str,
) -> str:
    brand = str(settings.get("brand_name") or "PTT Advertising Solutions").strip()
    system = (
        f"Bạn là trợ lý THỰC THI công việc CRM của {brand}. "
        "Ưu tiên làm việc (trả số liệu, xác nhận đã xuất file) — KHÔNG hướng dẫn bấm menu UI trừ khi user hỏi «hướng dẫn / cách». "
        "Trả lời ngắn, tiếng Việt, markdown gọn. Không bịa số liệu.\n\n"
        f"{CRM_KNOWLEDGE}"
        f"{_context_block(context)}"
    )
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    for m in history[-10:]:
        role = str(m.get("role") or "")
        text = str(m.get("text") or "").strip()[:2000]
        if not text:
            continue
        if role == "user":
            messages.append({"role": "user", "content": text})
        elif role in ("assistant", "bot"):
            messages.append({"role": "assistant", "content": text})
    messages.append({"role": "user", "content": question[:2000]})

    payload = json.dumps(
        {
            "model": (
                os.environ.get("OPENAI_MODEL")
                or os.environ.get("AI_CHAT_MODEL")
                or "gpt-4o-mini"
            ),
            "messages": messages,
            "max_tokens": 1800,
            "temperature": 0.45,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return str(data["choices"][0]["message"]["content"]).strip()


def _openai_error_hint(exc: Exception) -> str:
    import urllib.error

    if isinstance(exc, urllib.error.HTTPError):
        if exc.code == 429:
            return "429 — vượt quota hoặc rate limit OpenAI"
        if exc.code == 401:
            return "401 — API key không hợp lệ"
        return f"HTTP {exc.code}"
    return type(exc).__name__


def build_crm_assistant_reply(
    question: str,
    history: list[dict[str, Any]] | None,
    settings: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> str:
    text = str(question or "").strip()
    if not text:
        return "Vui lòng nhập câu hỏi về quy trình CRM hoặc case đang xử lý."
    if len(text) > 4000:
        text = text[:4000]

    s = settings or {}
    matched = _rule_based_reply(text, context)
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()

    if matched:
        return matched

    if api_key:
        try:
            return _openai_reply(text, history or [], s, context, api_key)
        except Exception as exc:
            api_hint = _openai_error_hint(exc)
            fallback = _rule_based_reply(text, context)
            if fallback:
                return (
                    f"{fallback}\n\n"
                    f"_OpenAI tạm thời không phản hồi ({api_hint}) — đã dùng playbook nội bộ._"
                )
            return (
                f"Cảm ơn bạn đã hỏi về «{text[:80]}{'…' if len(text) > 80 else ''}».\n\n"
                "Gợi ý nhanh: kiểm tra giai đoạn pipeline, SLA và cập nhật timeline trên case.\n\n"
                f"OpenAI đã cấu hình nhưng chưa trả lời được ({api_hint}). Thử lại sau hoặc hỏi «playbook 6 bước»."
            )

    fallback = _rule_based_reply(text, context)
    if fallback:
        return fallback

    return (
        f"Cảm ơn bạn đã hỏi về «{text[:80]}{'…' if len(text) > 80 else ''}».\n\n"
        "Thử các câu hỏi mẫu: «Playbook 6 bước», «SLA pipeline», «Script form landing».\n\n"
        "Thêm **OPENAI_API_KEY** vào PTT/.env để nhận tư vấn chi tiết hơn theo dữ liệu CRM."
    )


def build_crm_assistant_response(
    question: str,
    history: list[dict[str, Any]] | None,
    settings: dict[str, Any] | None,
    context: dict[str, Any] | None,
    conn: sqlite3.Connection,
    *,
    portal_staff_id: int | None = None,
    can_payroll_file: bool = False,
) -> dict[str, Any]:
    """Thực thi yêu cầu trước (file, số liệu) — không trả hướng dẫn dài."""
    ctx = context or {}

    if wants_payroll_export(question):
        if not can_payroll_file:
            return {
                "reply": "Không có quyền xuất bảng lương. Liên hệ HR / quản trị.",
                "files": [],
            }
        files = build_payroll_file_attachments(question, ctx, conn, portal_staff_id=portal_staff_id)
        if files:
            return {
                "reply": _payroll_action_message(
                    question, ctx, portal_staff_id=portal_staff_id
                ),
                "files": files,
            }
        payroll = ctx.get("payroll") if isinstance(ctx.get("payroll"), dict) else {}
        staff_list = payroll.get("staff_list") if isinstance(payroll, dict) else []
        _sid, _sq, _label, staff_err = _resolve_payroll_staff_filter(
            question, staff_list or [], portal_staff_id=portal_staff_id
        )
        if staff_err:
            return {"reply": staff_err, "files": []}
        y, m = parse_payroll_month_from_text(question)
        return {
            "reply": (
                f"Không có dữ liệu lương **{m:02d}/{y}**. "
                "Cần tính lương kỳ này trước (CRM → Chấm công & Lương)."
            ),
            "files": [],
        }

    if wants_daily_work_report_page(question):
        return {
            "reply": (
                "**Báo cáo công việc hàng ngày** — nhập báo cáo và xem lịch sử tại "
                "[CRM → Báo cáo công việc](/crm/daily-reports). "
                "Chọn ngày, thêm công việc và bấm **Lưu báo cáo**; mỗi ngày một báo cáo / nhân viên."
            ),
            "files": [],
        }

    if wants_daily_work_report_template(question):
        files = build_daily_work_report_file_attachments(
            question, portal_staff_id=portal_staff_id
        )
        if files:
            return {
                "reply": (
                    "**Báo cáo công việc hàng ngày** — nhập và xem lịch sử tại "
                    "[CRM → Báo cáo công việc](/crm/daily-reports). "
                    "Hoặc tải mẫu Excel bên dưới."
                ),
                "files": files,
            }

    reply = build_crm_assistant_reply(question, history, settings, ctx)
    return {"reply": reply, "files": []}


def _role_label(role: str) -> str:
    return "Bạn" if role == "user" else "Trợ lý CRM"


def build_crm_export_markdown(
    messages: list[dict[str, Any]], *, brand: str = "PTT Advertising Solutions"
) -> str:
    from datetime import timezone

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Bản ghi trợ lý CRM — {brand}",
        f"_Xuất lúc {ts}_",
        "",
    ]
    for m in messages:
        role = str(m.get("role") or "")
        text = str(m.get("text") or "").strip()
        if not text:
            continue
        lines.append(f"## {_role_label(role)}")
        lines.append("")
        lines.append(text)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_crm_export_html(
    messages: list[dict[str, Any]], *, brand: str = "PTT Advertising Solutions"
) -> str:
    from datetime import timezone
    from html import escape

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    parts = [
        "<!DOCTYPE html><html lang='vi'><head><meta charset='utf-8'>",
        f"<title>Trợ lý CRM — {escape(brand)}</title>",
        "<style>body{font-family:Inter,system-ui,sans-serif;max-width:820px;margin:2rem auto;padding:0 1rem;color:#13233f}"
        "h1{color:#2f7238}.msg{margin:1.25rem 0;padding:1rem;border:1px solid #d8deeb;border-radius:12px;background:#f6faf7}"
        ".meta{font-size:.75rem;color:#59657d;text-transform:uppercase;margin-bottom:.5rem}</style></head><body>",
        f"<h1>Trợ lý CRM — {escape(brand)}</h1>",
        f"<p><em>Xuất lúc {escape(ts)}</em></p>",
    ]
    for m in messages:
        role = str(m.get("role") or "")
        text = str(m.get("text") or "").strip()
        if not text:
            continue
        body = escape(text).replace("\n", "<br>")
        parts.append(f"<div class='msg'><div class='meta'>{escape(_role_label(role))}</div>{body}</div>")
    parts.append("</body></html>")
    return "\n".join(parts)
