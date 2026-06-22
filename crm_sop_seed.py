"""Seed SOP templates mặc định — Launch campaign 14 ngày."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

LAUNCH_CAMPAIGN_TEMPLATE_CODE = "MKT-LAUNCH-14D"

LAUNCH_CAMPAIGN_STEPS: tuple[dict[str, Any], ...] = (
    {
        "title": "Brief chiến dịch & mục tiêu KPI",
        "description": "Xác nhận dự án BĐS, segment, CPL/MQL target, ngân sách và timeline 14 ngày.",
        "offset_days": 0,
        "duration_days": 1,
        "role": "strategy",
        "checklist": [
            "Chốt mục tiêu: lead/tháng, CPL, MQL",
            "Cập nhật tab Marketing trên RE Projects",
            "Ghi campaign trên Hub MKT",
        ],
    },
    {
        "title": "Duyệt ngân sách & phân bổ kênh",
        "description": "Duyệt budget_breakdown (FB/Google/Zalo/Event) và sync Kế toán dự án.",
        "offset_days": 0,
        "duration_days": 1,
        "role": "approver",
        "checklist": [
            "Duyệt NS trên crm_re_projects_budget",
            "Sync KH → ngân sách (nếu cần)",
            "Khóa cap chi/ngày trên ads",
        ],
    },
    {
        "title": "Setup tracking & CRM",
        "description": "Pixel/GA4, UTM chuẩn, webhook Facebook Form → lead đúng dự án.",
        "offset_days": 1,
        "duration_days": 2,
        "role": "analytics",
        "checklist": [
            "Test webhook FB (ptt_fb_webhook_probe)",
            "Map Form ID → dự án",
            "Kiểm tra lead test vào /crm/leads",
        ],
    },
    {
        "title": "Brief landing & creative",
        "description": "Thông điệp, CTA, form fields, policy quảng cáo BĐS.",
        "offset_days": 2,
        "duration_days": 2,
        "role": "content",
        "checklist": [
            "Key message theo STP dự án",
            "Landing mobile-first",
            "Legal disclaimer / pháp lý dự án",
        ],
    },
    {
        "title": "Sản xuất creative (static/video)",
        "description": "Banner, video 15–30s, carousel theo phân khu/loại hình.",
        "offset_days": 3,
        "duration_days": 3,
        "role": "design",
        "checklist": [
            "≥3 biến thể creative",
            "Export đúng spec Meta/Google",
            "Pre-approval nội bộ",
        ],
    },
    {
        "title": "QA tracking & policy ads",
        "description": "Test conversion, Events Manager, tuân thủ chính sách quảng cáo BĐS.",
        "offset_days": 5,
        "duration_days": 1,
        "role": "analytics",
        "checklist": [
            "Lead test end-to-end",
            "Không vi phạm targeting cấm",
            "Backup creative nếu bị từ chối",
        ],
    },
    {
        "title": "Setup & cấu hình campaign Ads",
        "description": "Cấu trúc campaign/adset/ad, audience, budget pacing.",
        "offset_days": 6,
        "duration_days": 1,
        "role": "ads",
        "checklist": [
            "Campaign structure theo funnel",
            "Audience lookalike / interest",
            "Daily budget + bid strategy",
        ],
    },
    {
        "title": "Soft launch — test CPA/CPL",
        "description": "Chạy thử 2–3 ngày, budget thấp, đo CPL và chất lượng lead.",
        "offset_days": 7,
        "duration_days": 2,
        "role": "ads",
        "checklist": [
            "Spend ≤20% ngân sách tuần",
            "Review lead scoring sau 24h",
            "Pause adset CPA vượt ngưỡng",
        ],
    },
    {
        "title": "Scale kênh đạt target",
        "description": "Tăng budget kênh đạt CPL/CPA target ≥3 ngày liên tiếp.",
        "offset_days": 9,
        "duration_days": 2,
        "role": "ads",
        "checklist": [
            "Scale +20%/ngày tối đa",
            "Giữ ít nhất 2 kênh song song",
            "Ghi dòng tiền chi ads vào Kế toán",
        ],
    },
    {
        "title": "Nurture lead D0–D7",
        "description": "Email/Zalo nurture, remarketing visitor chưa để lại SĐT.",
        "offset_days": 8,
        "duration_days": 3,
        "role": "content",
        "checklist": [
            "Sequence D0, D2, D5",
            "Remarketing 7 ngày",
            "Theo dõi MQL rate",
        ],
    },
    {
        "title": "Handoff MQL → Sales",
        "description": "Họp sync Sales–MKT: lead chất lượng, SLA, phản hồi telesales.",
        "offset_days": 10,
        "duration_days": 1,
        "role": "strategy",
        "checklist": [
            "Báo cáo MQL tuần",
            "Lead quá hạn SLA = 0",
            "Feedback loop từ Sales",
        ],
    },
    {
        "title": "Báo cáo tuần 1 & tối ưu",
        "description": "CPL, CPA, ROI sơ bộ; điều chỉnh creative/audience.",
        "offset_days": 11,
        "duration_days": 2,
        "role": "analytics",
        "checklist": [
            "Export Excel kế toán MKT",
            "Tab Marketing trên RE cập nhật actual",
            "AI hỏi: chi phí marketing / so sánh KH vs TT",
        ],
    },
    {
        "title": "Refresh creative (chống fatigue)",
        "description": "Thay creative nếu CTR giảm >20% hoặc frequency cao.",
        "offset_days": 13,
        "duration_days": 1,
        "role": "design",
        "checklist": [
            "Kiểm tra frequency adset",
            "Upload creative mới",
            "A/B headline/CTA",
        ],
    },
    {
        "title": "Retro & đóng sprint 14 ngày",
        "description": "Tổng kết ROMI, bài học, quyết định scale/pause cho tuần tiếp.",
        "offset_days": 14,
        "duration_days": 1,
        "role": "approver",
        "checklist": [
            "Đóng SOP run hoặc chuyển sang tuần 2",
            "Cập nhật rủi ro MKT (nếu có)",
            "Lưu playbook vào Hub campaign notes",
        ],
    },
)


def seed_launch_campaign_sop_template(conn: sqlite3.Connection) -> dict[str, Any]:
    """Tạo template SOP Launch 14 ngày nếu chưa có (theo code MKT-LAUNCH-14D)."""
    existing = conn.execute(
        "SELECT id FROM crm_sop_templates WHERE lower(trim(code)) = lower(trim(?))",
        (LAUNCH_CAMPAIGN_TEMPLATE_CODE,),
    ).fetchone()
    if existing:
        tid = int(existing["id"])
        step_count = conn.execute(
            "SELECT COUNT(*) AS n FROM crm_sop_steps WHERE template_id = ?",
            (tid,),
        ).fetchone()
        return {
            "template_id": tid,
            "created": False,
            "steps": int(step_count["n"]) if step_count else 0,
        }

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date = ts[:10]
    cur = conn.execute(
        """
        INSERT INTO crm_sop_templates (code, name, channel, description, notes, active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 1, ?, ?)
        """,
        (
            LAUNCH_CAMPAIGN_TEMPLATE_CODE,
            "Launch campaign BĐS — 14 ngày",
            "ads",
            "Playbook triển khai chiến dịch quảng cáo BĐS: brief → tracking → creative → ads → MQL → báo cáo.",
            "Template hệ thống PTT — dùng với Hub Chiến dịch + RE Projects Marketing + Kế toán MKT.",
            date,
            ts,
        ),
    )
    tid = int(cur.lastrowid)
    for pos, step in enumerate(LAUNCH_CAMPAIGN_STEPS):
        checklist = json.dumps(step.get("checklist") or [], ensure_ascii=False)
        conn.execute(
            """
            INSERT INTO crm_sop_steps (
                template_id, position, title, description, offset_days, duration_days,
                role, required, checklist_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                tid,
                pos,
                str(step["title"])[:500],
                str(step.get("description") or "")[:8000],
                int(step.get("offset_days") or 0),
                max(1, int(step.get("duration_days") or 1)),
                str(step.get("role") or "any"),
                checklist[:4000],
                ts,
                ts,
            ),
        )
    return {"template_id": tid, "created": True, "steps": len(LAUNCH_CAMPAIGN_STEPS)}
