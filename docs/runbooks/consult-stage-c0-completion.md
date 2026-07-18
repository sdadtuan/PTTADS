# Phase C0 — Checklist hoàn thành

**Mục tiêu C0:** SOP + đào tạo AM — **không code** — trước Phase C1 (Consult Brief).

**Cập nhật:** 2026-06-30

---

## Deliverables kỹ thuật / tài liệu

| # | Hạng mục | File | Trạng thái |
|---|----------|------|------------|
| D1 | Spec thiết kế Consult | `docs/specs/2026-06-30-consult-stage-system-design.md` | ✅ Xong |
| D2 | Kế hoạch C1–C6 | `docs/superpowers/plans/2026-06-30-consult-stage-system.md` | ✅ Xong |
| D3 | Script + PPT đào tạo | `scripts/generate_consult_stage_pptx.py` → `docs/Consult_Stage_Service_Delivery.pptx` | ✅ Xong |
| D4 | SOP AM (đầy đủ) | `docs/runbooks/consult-stage-am-sop.md` | ✅ Xong |
| D5 | Phụ lục task 12 DV | `docs/runbooks/consult-stage-service-tasks.md` (auto-gen) | ✅ Xong |
| D6 | Hướng dẫn facilitator | `docs/runbooks/consult-stage-training-guide.md` | ✅ Xong |
| D7 | BANT sign-off template | `docs/runbooks/consult-stage-bant-signoff.md` | ✅ Xong (chờ ký) |
| D8 | Hub tài liệu CRM | `docs/crm/README.md` | ✅ Xong |
| D9 | Script phụ lục | `scripts/generate_consult_runbook_appendix.py` | ✅ Xong |

---

## Việc cần người (không tự động)

| # | Việc | Owner | Trạng thái |
|---|------|-------|------------|
| H1 | Review slide deck với Sales lead | Sales lead | ☐ Chưa |
| H2 | Tổ chức buổi training 45p (theo training guide) | Sales lead / Facilitator | ☐ Chưa |
| H3 | AM ký xác nhận đã đọc SOP | AM team | ☐ Chưa |
| H4 | Director ký BANT sign-off (mục Q1–Q6) | Director | ☐ Chưa |
| H5 | Ghi kết quả Q1–Q6 vào sign-off doc | CRM admin | ☐ Chưa |

---

## Tiêu chí đóng Phase C0

Phase C0 coi là **xong** khi:

- [x] Tất cả deliverable D1–D9 có trên repo
- [ ] H1 — Sales lead review PPT (ghi ngày bên dưới)
- [ ] H2 — ≥1 buổi training đã tổ chức
- [ ] H4 — BANT sign-off có chữ ký Director **hoặc** email approve lưu nội bộ

**Ghi chú review Sales lead:**

| Ngày | Người review | Ghi chú |
|------|--------------|---------|
| | | |

**Ghi chú buổi training:**

| Ngày | Số AM | Facilitator | Ghi chú |
|------|-------|-------------|---------|
| | | | |

---

## Mở rộng đã ghi nhận (chờ xác nhận trước C3)

Policy đã xác nhận qua CRM (2026-06-30) — ghi trong [consult-stage-bant-signoff.md](./consult-stage-bant-signoff.md):

- BANT: Go ≥22 · Nurture 16–21 (block Consult) · No-Go <16
- No-Go → block Consult (Director override)
- Go → bắt buộc Intake **in_person** trước Consult sâu
- Consult **miễn phí** — không thu phí tư vấn/audit (Q6)
- **P0 (code):** `owner_id` lead → `assigned_am` lifecycle (tạo lifecycle, phân lại lead, backfill)
- **Chưa xác nhận:** ngưỡng VND deal enterprise cần Director (Q4)

Triển khai code gate tại **Phase C3** sau chữ ký Director trên sign-off doc.

---

## Bước tiếp theo

Sau khi H4 (hoặc approve nội bộ) → bắt đầu **Phase C1**: `crm_svc_consult_bridge.py` + Consult Brief panel.

---

*PTT CRM · Consult Stage Program*
