"""AI cho Lead — tìm kiếm, tóm tắt, gợi ý (rule-based + OpenAI tùy chọn)."""
from __future__ import annotations

import json
import os
import re
import sqlite3
from typing import Any

from crm_lead_store import (
    LEAD_LEVEL_LABELS,
    activity_row_to_dict,
    fetch_lead_activities,
    fetch_lead_by_id,
    fetch_leads,
    is_sla_overdue,
    lead_row_to_dict,
    log_ai_action,
    normalize_level,
)
from crm_project_leads import _UNSET


def _norm(text: str) -> str:
    s = str(text or "").lower()
    for a, b in (
        ("àáạảãâầấậẩẫăằắặẳẵ", "a"),
        ("èéẹẻẽêềếệểễ", "e"),
        ("ìíịỉĩ", "i"),
        ("òóọỏõôồốộổỗơờớợởỡ", "o"),
        ("ùúụủũưừứựửữ", "u"),
        ("ỳýỵỷỹ", "y"),
    ):
        for ch in a:
            s = s.replace(ch, b)
    s = s.replace("đ", "d")
    return re.sub(r"\s+", " ", s).strip()


def _openai_json(prompt: str, system: str) -> dict[str, Any] | None:
    key = str(os.environ.get("OPENAI_API_KEY") or "").strip()
    if not key:
        return None
    try:
        import urllib.request

        body = json.dumps(
            {
                "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            }
        ).encode()
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=body,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception:
        return None


def _ai_fetch_kw(
    *,
    owner_id: int | None = None,
    staff_portal_id: int | None = None,
) -> dict[str, Any]:
    if staff_portal_id is not None:
        return {"staff_portal_id": int(staff_portal_id)}
    return {"owner_id": owner_id}


def _ai_parse_segment_filters(
    conn: sqlite3.Connection,
    question: str,
    *,
    re_project_id: int | None = None,
) -> tuple[str, str]:
    """Trích product_line / zone từ câu hỏi tiếng Việt."""
    q = _norm(question)
    line = ""
    zone = ""
    try:
        from crm_re_projects import PRODUCT_LINE_LABELS

        for code, label in PRODUCT_LINE_LABELS.items():
            lbl = _norm(label)
            if lbl and lbl in q:
                line = code
                break
            if code.replace("_", " ") in q:
                line = code
                break
        aliases = {
            "can ho": "can_ho",
            "shop house": "shophouse",
            "shophouse": "shophouse",
            "biet thu": "biet_thu",
            "lien ke": "lien_ke",
            "nha pho": "lien_ke",
            "dat nen": "dat_nen",
        }
        if not line:
            for alias, code in aliases.items():
                if alias in q:
                    line = code
                    break
    except Exception:
        pass
    if re_project_id:
        try:
            from crm_project_deep import list_project_zones

            for z in list_project_zones(conn, int(re_project_id)):
                if _norm(z) in q:
                    zone = z
                    break
        except Exception:
            pass
    return line, zone


def ai_suggest_products_for_lead(
    conn: sqlite3.Connection,
    lead_id: int,
    *,
    limit: int = 5,
    created_by: str = "",
    ts: str = "",
) -> dict[str, Any]:
    """Gợi ý căn trống phù hợp segment lead (dòng SP / phân khu / text quan tâm)."""
    row = fetch_lead_by_id(conn, lead_id)
    if row is None:
        return {"error": "Không tìm thấy lead.", "products": [], "answer": ""}
    lead = lead_row_to_dict(row)
    project_id = lead.get("re_project_id")
    if not project_id:
        return {
            "lead_id": lead_id,
            "products": [],
            "answer": "Lead chưa gán dự án BĐS — không gợi ý được mã căn.",
            "confidence": 0.5,
            "fallback_used": True,
        }
    from crm_project_deep import search_available_products

    line = str(lead.get("product_line") or "")
    zone = str(lead.get("zone") or "")
    interest = str(lead.get("product_interest") or "").strip()
    # Text quan tâm thường mô tả nhu cầu — chỉ dùng làm q khi chưa có segment rõ.
    search_q = interest if interest and not line and not zone else ""

    products = search_available_products(
        conn,
        int(project_id),
        q=search_q,
        product_line=line,
        zone=zone,
        status="available",
        limit=max(1, min(int(limit), 20)),
    )
    if not products and interest:
        products = search_available_products(
            conn,
            int(project_id),
            q=interest,
            product_line=line,
            zone=zone,
            status="available",
            limit=max(1, min(int(limit), 20)),
        )
    seg_bits = [
        lead.get("product_line_label") or lead.get("product_line"),
        lead.get("zone"),
    ]
    seg = " · ".join(str(x) for x in seg_bits if x)
    if products:
        answer = f"Gợi ý **{len(products)}** căn trống" + (f" ({seg})" if seg else "") + "."
    else:
        answer = "Không có căn trống khớp segment lead — thử nới phân khu hoặc dòng SP."
    out = {
        "lead_id": lead_id,
        "products": products,
        "answer": answer,
        "confidence": 0.85 if products else 0.45,
        "fallback_used": not bool(products),
        "references": [{"type": "product", "id": p["id"], "unit_code": p.get("unit_code")} for p in products[:5]],
    }
    if ts:
        log_ai_action(
            conn,
            lead_id=lead_id,
            action="suggest_products",
            input_text=f"lead:{lead_id}",
            output=out,
            confidence=out["confidence"],
            fallback_used=out["fallback_used"],
            created_by=created_by,
            ts=ts,
        )
    return out


def _match_version_codes(
    conn: sqlite3.Connection,
    question: str,
    project_id: int,
) -> list[str]:
    from crm_re_price_lists import list_all_version_codes

    q = _norm(question)
    q_compact = q.replace("-", "").replace("_", "").replace(" ", "")
    found: list[str] = []
    for code in list_all_version_codes(conn, int(project_id)):
        c = str(code or "").strip()
        if not c:
            continue
        cn = _norm(c)
        cc = cn.replace("-", "").replace("_", "").replace(" ", "")
        if cn in q or cc in q_compact:
            found.append(c)
    return found


def ai_price_list_query(
    conn: sqlite3.Connection,
    question: str,
    *,
    re_project_id: int,
    created_by: str = "",
    ts: str = "",
) -> dict[str, Any]:
    """AI tra cứu bảng giá: căn đang áp version, so sánh Dot1 vs Dot2."""
    from crm_re_price_lists import compare_price_lists, products_on_price_version

    q = _norm(question)
    codes = _match_version_codes(conn, question, int(re_project_id))
    compare_mode = any(k in q for k in ("so sanh", "compare", "doi chieu", "khac nhau")) or " vs " in question.lower()

    if compare_mode:
        va = vb = ""
        if len(codes) >= 2:
            va, vb = codes[0], codes[1]
        elif len(codes) == 1:
            parts = [p.strip() for p in question.replace("—", "-").split(" vs ") if p.strip()]
            if len(parts) >= 2:
                va, vb = parts[0], parts[1]
        if not va or not vb:
            return {
                "answer": "Cần hai mã version (VD: «So sánh giá Dot1-2026 vs Dot2-2026»).",
                "products": [],
                "compare": None,
                "confidence": 0.4,
                "fallback_used": True,
            }
        cmp = compare_price_lists(conn, int(re_project_id), va, vb)
        sm = cmp.get("summary") or {}
        answer = (
            f"So sánh **{va}** vs **{vb}**: "
            f"{sm.get('both', 0)} căn chung, "
            f"{sm.get('increased', 0)} tăng giá, {sm.get('decreased', 0)} giảm, "
            f"{sm.get('unchanged', 0)} không đổi."
        )
        if sm.get("only_a"):
            answer += f" Chỉ có ở {va}: {sm['only_a']} căn."
        if sm.get("only_b"):
            answer += f" Chỉ có ở {vb}: {sm['only_b']} căn."
        out = {
            "answer": answer,
            "products": [],
            "compare": cmp,
            "references": [{"type": "price_version", "code": va}, {"type": "price_version", "code": vb}],
            "confidence": 0.9,
            "fallback_used": False,
        }
    else:
        version = codes[0] if codes else ""
        if not version:
            for token in question.replace(",", " ").split():
                t = token.strip()
                if t.lower().startswith("dot") or "-20" in t.lower():
                    version = t
                    break
        if not version:
            return {
                "answer": "Chọn dự án và nêu mã version (VD: «Căn nào đang áp giá Dot2-2026?»).",
                "products": [],
                "compare": None,
                "confidence": 0.4,
                "fallback_used": True,
            }
        products = products_on_price_version(conn, int(re_project_id), version, limit=50)
        answer = f"**{len(products)}** căn đang áp giá **{version}**."
        if products:
            preview = ", ".join(p.get("unit_code") or "?" for p in products[:8])
            if len(products) > 8:
                preview += "…"
            answer += f" VD: {preview}."
        else:
            answer += " Chưa có sản phẩm nào gắn đợt giá này — kiểm tra đã «Áp dụng bảng giá» chưa."
        out = {
            "answer": answer,
            "products": products,
            "compare": None,
            "version_code": version,
            "references": [{"type": "product", "id": p["id"], "unit_code": p.get("unit_code")} for p in products[:10]],
            "confidence": 0.88 if products else 0.5,
            "fallback_used": not bool(products),
        }

    if ts:
        log_ai_action(
            conn,
            lead_id=None,
            action="price_list_query",
            input_text=question[:500],
            output={"answer": out["answer"], "version": out.get("version_code")},
            confidence=out["confidence"],
            fallback_used=out["fallback_used"],
            created_by=created_by,
            ts=ts,
        )
    return out


def ai_search_leads(
    conn: sqlite3.Connection,
    question: str,
    *,
    owner_id: int | None = None,
    staff_portal_id: int | None = None,
    re_project_id: int | None | object = _UNSET,
    created_by: str = "",
    ts: str = "",
) -> dict[str, Any]:
    """FR-10: Tìm lead bằng ngôn ngữ tự nhiên."""
    q = _norm(question)
    fallback = False
    results: list[dict[str, Any]] = []
    references: list[dict[str, Any]] = []
    answer = ""
    project_note = ""
    fetch_kw = _ai_fetch_kw(owner_id=owner_id, staff_portal_id=staff_portal_id)
    if re_project_id is not _UNSET and isinstance(re_project_id, int):
        from crm_re_projects import fetch_project

        proj = fetch_project(conn, int(re_project_id))
        if proj:
            project_note = f" (dự án: {proj.get('name') or proj.get('code')})"

    pid = int(re_project_id) if isinstance(re_project_id, int) else None
    seg_line, seg_zone = _ai_parse_segment_filters(conn, question, re_project_id=pid)
    seg_note = ""
    if seg_line or seg_zone:
        from crm_re_projects import PRODUCT_LINE_LABELS

        bits = []
        if seg_line:
            bits.append(PRODUCT_LINE_LABELS.get(seg_line, seg_line))
        if seg_zone:
            bits.append(seg_zone)
        seg_note = f" — segment: {', '.join(bits)}"

    if any(k in q for k in ("giu cho", "hold", "dang giu", "ma can")):
        rows = fetch_leads(
            conn,
            re_project_id=re_project_id,
            limit=200,
            **fetch_kw,
        )
        held = [
            lead_row_to_dict(r, conn)
            for r in rows
            if dict(r).get("re_product_id")
            and str(dict(r).get("re_product_status") or "") == "hold"
        ]
        if "chua" in q or "trong" in q or "available" in q:
            from crm_project_deep import search_available_products

            avail: list[dict[str, Any]] = []
            if pid:
                avail = search_available_products(
                    conn,
                    pid,
                    product_line=seg_line,
                    zone=seg_zone,
                    limit=15,
                )
            results = avail[:15] if avail else held[:15]
            if avail:
                answer = f"**{len(avail)}** căn trống{project_note}{seg_note}."
                references = [{"type": "product", "id": p["id"], "unit_code": p.get("unit_code")} for p in results[:10]]
            else:
                results = held[:15]
                answer = f"**{len(held)}** lead đang giữ chỗ sản phẩm{project_note}."
        else:
            results = held[:20]
            answer = f"**{len(held)}** lead đang giữ chỗ SP{project_note}."
    elif seg_line or seg_zone or any(
        k in q for k in ("dong sp", "phan khu", "shophouse", "can ho", "biet thu", "lien ke", "segment")
    ):
        rows = fetch_leads(
            conn,
            re_project_id=re_project_id,
            product_line=seg_line or None,
            zone=seg_zone or None,
            limit=30,
            **fetch_kw,
        )
        results = [lead_row_to_dict(r) for r in rows]
        answer = (
            f"**{len(results)}** lead khớp segment{seg_note}{project_note}."
            if results
            else f"Không có lead khớp segment{seg_note}{project_note}."
        )
        fallback = not bool(results)
    elif pid and any(
        k in q
        for k in (
            "ke toan",
            "dong tien",
            "thu chi",
            "loi nhuan",
            "chi phi marketing",
            "ngan sach",
            "p&l",
            " pl ",
            "du bao",
            "du doan",
            "rui ro",
            "nguy co",
            "runway",
            "forecast",
        )
    ):
        from crm_re_project_accounting import ai_project_finance_query

        fin_out = ai_project_finance_query(
            conn,
            question,
            re_project_id=pid,
            created_by=created_by,
            ts="",
        )
        answer = fin_out.get("answer") or ""
        fallback = bool(fin_out.get("fallback_used"))
        if ts:
            log_ai_action(
                conn,
                lead_id=None,
                action="search",
                input_text=question[:500],
                output={"answer": answer, "finance": True},
                confidence=fin_out.get("confidence", 0.7),
                fallback_used=fallback,
                created_by=created_by,
                ts=ts,
            )
        return {
            "answer": answer,
            "leads": [],
            "products": [],
            "references": [],
            "dashboard": fin_out.get("dashboard"),
            "fallback_used": fallback,
            "confidence": fin_out.get("confidence", 0.7),
        }
    elif pid and any(
        k in q
        for k in (
            "dot",
            "do gia",
            "dot gia",
            "bang gia",
            "price",
            "ap gia",
            "dang ap",
            "so sanh gia",
            "version gia",
        )
    ):
        pl_out = ai_price_list_query(
            conn,
            question,
            re_project_id=pid,
            created_by=created_by,
            ts="",
        )
        answer = pl_out.get("answer") or ""
        results = pl_out.get("products") or []
        references = pl_out.get("references") or []
        fallback = bool(pl_out.get("fallback_used"))
        if ts:
            log_ai_action(
                conn,
                lead_id=None,
                action="search",
                input_text=question[:500],
                output={"answer": answer, "price_list": True},
                confidence=pl_out.get("confidence", 0.7),
                fallback_used=fallback,
                created_by=created_by,
                ts=ts,
            )
        return {
            "answer": answer,
            "leads": [],
            "products": results,
            "references": references,
            "compare": pl_out.get("compare"),
            "fallback_used": fallback,
            "confidence": pl_out.get("confidence", 0.7),
        }
    elif any(k in q for k in ("qua han", "sla", "chua xu ly")):
        rows = fetch_leads(conn, re_project_id=re_project_id, limit=200, **fetch_kw)
        overdue = [
            lead_row_to_dict(r)
            for r in rows
            if is_sla_overdue(str(r["status"]), str(r["status_entered_at"] or ""))
        ]
        results = overdue[:20]
        answer = f"Có **{len(overdue)}** lead quá hạn SLA{project_note}." if overdue else f"Không có lead quá hạn SLA{project_note}."
    elif any(k in q for k in ("form chua map", "form chưa map", "webhook facebook", "facebook chua map", "form facebook")):
        from crm_project_webhooks import list_unmapped_facebook_forms, suggest_facebook_form_project

        unmapped = list_unmapped_facebook_forms(conn, limit=15)
        suggestions = []
        for row in unmapped[:5]:
            sug = suggest_facebook_form_project(conn, row["form_id"])
            if sug:
                suggestions.append(sug)
        results = unmapped
        if unmapped:
            answer = (
                f"Có **{len(unmapped)}** Form Facebook chưa map dự án{project_note}. "
                "Thêm Form ID trong Dự án BĐS → Lead & Webhook."
            )
            if suggestions:
                s0 = suggestions[0]
                answer += (
                    f" Gợi ý: Form {s0['form_id']} → "
                    f"{s0.get('suggested_project_name') or s0.get('suggested_project_code')}."
                )
        else:
            answer = f"Không có form Facebook pending chưa map{project_note}."
        refs = [{"type": "facebook_form", "form_id": r.get("form_id"), "pending_count": r.get("pending_count")} for r in results[:10]]
        references.extend(refs)
    elif any(k in q for k in ("chua gan", "chua phan cong", "chua co owner", "chua assign")):
        rows = fetch_leads(conn, re_project_id=re_project_id, limit=200, **fetch_kw)
        unassigned = [lead_row_to_dict(r) for r in rows if not r["owner_id"] and not r["is_duplicate"]]
        results = unassigned[:20]
        answer = (
            f"Có **{len(unassigned)}** lead chưa gán owner{project_note}."
            if unassigned
            else f"Không có lead chưa gán owner{project_note}."
        )
    elif any(k in q for k in ("hot", "nong", "uu tien")):
        rows = fetch_leads(conn, re_project_id=re_project_id, level="hot", limit=20, **fetch_kw)
        results = [lead_row_to_dict(r) for r in rows]
        answer = f"**{len(results)}** lead Hot đang cần ưu tiên{project_note}."
    elif any(k in q for k in ("chot", "kha nang")):
        rows = fetch_leads(conn, re_project_id=re_project_id, limit=50, **fetch_kw)
        scored = sorted([lead_row_to_dict(r) for r in rows], key=lambda x: (-x["lead_score"], x["full_name"]))
        results = scored[:10]
        answer = f"Top lead có điểm cao nhất{project_note}:"
    elif "goi" in q or "lien he" in q:
        rows = fetch_leads(conn, re_project_id=re_project_id, q=question, limit=5, **fetch_kw)
        if rows:
            lid = int(rows[0]["id"])
            acts = fetch_lead_activities(conn, lid, limit=50)
            calls = [a for a in acts if str(a["activity_type"]) == "call"]
            lead = lead_row_to_dict(rows[0])
            results = [lead]
            answer = f"Lead **{lead['full_name']}** đã được gọi **{len(calls)}** lần."
        else:
            answer = "Không tìm thấy lead phù hợp."
    else:
        rows = fetch_leads(conn, re_project_id=re_project_id, q=question, limit=15, **fetch_kw)
        results = [lead_row_to_dict(r) for r in rows]
        answer = (
            f"Tìm thấy **{len(results)}** lead{project_note}."
            if results
            else f"Không tìm thấy lead phù hợp{project_note}."
        )
        fallback = not bool(results)

    if not references:
        references = [
            {"type": "lead", "id": r["id"], "name": r["full_name"]}
            for r in results[:10]
            if r.get("id") is not None
        ]

    out = {
        "answer": answer,
        "leads": results,
        "references": references,
        "fallback_used": fallback,
        "confidence": 0.85 if results else 0.4,
    }
    if ts:
        first_id = results[0].get("id") if len(results) == 1 else None
        log_ai_action(
            conn,
            lead_id=int(first_id) if first_id is not None else None,
            action="search",
            input_text=question,
            output=out,
            confidence=out["confidence"],
            fallback_used=fallback,
            created_by=created_by,
            ts=ts,
        )
    return out


def ai_summarize_lead(
    conn: sqlite3.Connection,
    lead_id: int,
    *,
    created_by: str = "",
    ts: str = "",
) -> dict[str, Any]:
    """FR-12: Tóm tắt lead."""
    row = fetch_lead_by_id(conn, lead_id)
    if row is None:
        return {"error": "Không tìm thấy lead.", "summary": ""}
    lead = lead_row_to_dict(row)
    acts = [activity_row_to_dict(a) for a in fetch_lead_activities(conn, lead_id, limit=30)]
    fallback = True
    blockers = ""
    next_step = ""

    ai = _openai_json(
        json.dumps({"lead": lead, "activities": acts[:15]}, ensure_ascii=False),
        "Trợ lý CRM. Trả JSON: summary, blockers, next_step (tiếng Việt).",
    )
    if ai and ai.get("summary"):
        summary_text = str(ai["summary"])
        blockers = str(ai.get("blockers") or "")
        next_step = str(ai.get("next_step") or "")
        fallback = False
    else:
        last = acts[0] if acts else None
        calls = sum(1 for a in acts if a["activity_type"] == "call")
        blockers = lead.get("need") or "Chưa ghi nhận rõ."
        next_step = (last.get("next_action") if last else "") or "Liên hệ trong SLA."
        summary_text = (
            f"**{lead['full_name']}** — {lead['source_label']}, {lead['status_label']}, "
            f"{lead['lead_level_label']} (điểm {lead['lead_score']}). "
            f"Dự án: {lead.get('re_project_label') or 'Chưa gán'}. "
            f"Dòng SP: {lead.get('product_line_label') or '—'}, phân khu: {lead.get('zone') or '—'}. "
            f"Mã căn: {lead.get('re_product_label') or 'Chưa chọn'}"
            f"{' (giữ chỗ)' if lead.get('re_product_status') == 'hold' else ''}. "
            f"Nhu cầu: {lead['need'] or '—'}. {len(acts)} hoạt động ({calls} gọi). "
            f"Owner: {lead['owner_name'] or 'Chưa gán'}."
        )

    out = {
        "lead_id": lead_id,
        "summary": summary_text,
        "blockers": blockers,
        "next_step": next_step,
        "activity_count": len(acts),
        "references": [{"type": "lead", "id": lead_id}, *[{"type": "activity", "id": a["id"]} for a in acts[:5]]],
        "fallback_used": fallback,
        "confidence": 0.9 if not fallback else 0.75,
    }
    if ts:
        log_ai_action(
            conn,
            lead_id=lead_id,
            action="summary",
            input_text=f"lead:{lead_id}",
            output=out,
            confidence=out["confidence"],
            fallback_used=fallback,
            created_by=created_by,
            ts=ts,
        )
    return out


def ai_recommend_lead(
    conn: sqlite3.Connection,
    lead_id: int | None = None,
    *,
    owner_id: int | None = None,
    staff_portal_id: int | None = None,
    re_project_id: int | None | object = _UNSET,
    created_by: str = "",
    ts: str = "",
) -> dict[str, Any]:
    """Gợi ý next action và lead ưu tiên."""
    recommendations: list[dict[str, Any]] = []
    at_risk: list[dict[str, Any]] = []
    fetch_kw = _ai_fetch_kw(owner_id=owner_id, staff_portal_id=staff_portal_id)

    if lead_id is not None:
        row = fetch_lead_by_id(conn, lead_id)
        if row is None:
            return {"error": "Không tìm thấy lead.", "recommendations": []}
        lead = lead_row_to_dict(row)
        acts = fetch_lead_activities(conn, lead_id, limit=10)
        if not lead.get("owner_id") and lead.get("re_project_id"):
            from crm_project_leads import suggest_project_assignee

            sug = suggest_project_assignee(
                conn,
                int(lead["re_project_id"]),
                lead_level=str(lead.get("lead_level") or "warm"),
                product_line=str(lead.get("product_line") or ""),
                zone=str(lead.get("zone") or ""),
            )
            if sug:
                scope_detail = ""
                if lead.get("product_line_label") or lead.get("zone"):
                    scope_detail = (
                        f" (pool: {lead.get('product_line_label') or '—'}"
                        f"{(' · ' + str(lead.get('zone'))) if lead.get('zone') else ''})"
                    )
                recommendations.append(
                    {
                        "type": "assign",
                        "title": f"Gợi ý phân công: {sug['name']}",
                        "detail": (
                            f"NV tham gia dự án {lead.get('re_project_label') or ''}"
                            f"{scope_detail} ({sug.get('role_label') or 'sales'})"
                        ).strip(),
                        "lead_id": lead_id,
                        "staff_id": sug["staff_id"],
                    }
                )
        if lead.get("re_project_id") and not lead.get("re_product_id"):
            prod_sug = ai_suggest_products_for_lead(conn, lead_id, limit=3)
            for p in (prod_sug.get("products") or [])[:3]:
                recommendations.append(
                    {
                        "type": "product",
                        "title": f"Gợi ý căn: {p.get('unit_code') or p.get('id')}",
                        "detail": f"{p.get('zone') or '—'} · {p.get('product_line_label') or '—'} · {p.get('list_price_vnd') or 0:,}đ",
                        "lead_id": lead_id,
                        "product_id": p.get("id"),
                    }
                )
        if (
            lead.get("re_product_id")
            and str(lead.get("re_product_status") or "") != "hold"
        ):
            recommendations.append(
                {
                    "type": "hold",
                    "title": "Giữ chỗ sản phẩm",
                    "detail": f"Căn {lead.get('re_product_label') or lead.get('re_product_unit_code')} — bấm Giữ chỗ SP để tránh double-book.",
                    "lead_id": lead_id,
                    "product_id": lead.get("re_product_id"),
                }
            )
        if (
            not lead.get("re_project_id")
            and str(lead.get("source") or "") == "facebook"
        ):
            meta = lead.get("meta") if isinstance(lead.get("meta"), dict) else {}
            form_id = str(meta.get("facebook_form_id") or "").strip()
            if form_id:
                from crm_project_webhooks import suggest_facebook_form_project

                map_sug = suggest_facebook_form_project(conn, form_id)
                if map_sug:
                    recommendations.append(
                        {
                            "type": "webhook_map",
                            "title": "Map Form Facebook → dự án",
                            "detail": (
                                f"Form {form_id} → "
                                f"{map_sug.get('suggested_project_name') or map_sug.get('suggested_project_code')}"
                            ),
                            "lead_id": lead_id,
                            "form_id": form_id,
                            "project_id": map_sug.get("suggested_project_id"),
                        }
                    )
        if lead["sla_overdue"]:
            recommendations.append(
                {"type": "urgent", "title": "Quá hạn SLA", "detail": "Liên hệ ngay.", "lead_id": lead_id}
            )
        if not acts:
            recommendations.append(
                {"type": "action", "title": "Gọi lần đầu", "detail": "Xác nhận nhu cầu trong 4h.", "lead_id": lead_id}
            )
        elif lead["lead_level"] == "hot":
            recommendations.append(
                {"type": "action", "title": "Báo giá / demo", "detail": "Lead Hot — hành động trong 24h.", "lead_id": lead_id}
            )
        if not recommendations:
            recommendations.append(
                {"type": "nurture", "title": "Duy trì chăm sóc", "detail": "Cập nhật next action.", "lead_id": lead_id}
            )
    else:
        rows = fetch_leads(conn, re_project_id=re_project_id, limit=100, **fetch_kw)
        priority: list[tuple[int, dict[str, Any]]] = []
        for r in rows:
            ld = lead_row_to_dict(r)
            if ld["sla_overdue"]:
                priority.append((100 + ld["lead_score"], ld))
                at_risk.append({"lead_id": ld["id"], "name": ld["full_name"], "reason": "Quá hạn SLA"})
            elif ld["lead_level"] == "hot":
                priority.append((50 + ld["lead_score"], ld))
        priority.sort(key=lambda x: -x[0])
        for _, ld in priority[:5]:
            recommendations.append(
                {
                    "type": "priority",
                    "title": f"Ưu tiên: {ld['full_name']}",
                    "detail": f"{ld['lead_level_label']} — điểm {ld['lead_score']}",
                    "lead_id": ld["id"],
                }
            )

    out = {
        "recommendations": recommendations,
        "at_risk": at_risk,
        "fallback_used": not recommendations,
        "confidence": 0.8,
    }
    if ts:
        log_ai_action(
            conn,
            lead_id=lead_id,
            action="recommend",
            input_text=f"lead:{lead_id or 'all'}",
            output=out,
            confidence=0.8,
            fallback_used=not recommendations,
            created_by=created_by,
            ts=ts,
        )
    return out


def ai_classify_suggestion(
    conn: sqlite3.Connection,
    lead_id: int,
    *,
    created_by: str = "",
    ts: str = "",
) -> dict[str, Any]:
    """FR-11: Gợi ý hot/warm/cold — không ghi đè."""
    row = fetch_lead_by_id(conn, lead_id)
    if row is None:
        return {"error": "Không tìm thấy lead."}
    lead = lead_row_to_dict(row)
    suggested = normalize_level(lead["lead_level"])
    confidence = 0.7
    reason = f"Điểm {lead['lead_score']}, trạng thái {lead['status_label']}."
    if lead["lead_score"] >= 70:
        suggested, confidence, reason = "hot", 0.85, "Điểm cao + liên hệ đầy đủ."
    elif lead["lead_score"] < 35:
        suggested, confidence, reason = "cold", 0.75, "Điểm thấp / thiếu tín hiệu."
    out = {
        "lead_id": lead_id,
        "current_level": lead["lead_level"],
        "suggested_level": suggested,
        "suggested_label": LEAD_LEVEL_LABELS.get(suggested, suggested),
        "confidence": confidence,
        "reason": reason,
        "requires_confirm": True,
        "fallback_used": True,
    }
    if ts:
        log_ai_action(
            conn,
            lead_id=lead_id,
            action="classify",
            input_text=f"lead:{lead_id}",
            output=out,
            confidence=confidence,
            fallback_used=True,
            created_by=created_by,
            ts=ts,
        )
    return out
