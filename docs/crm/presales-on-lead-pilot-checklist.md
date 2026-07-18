# Checklist pilot — Pre-sales trên Lead (Phương án A)

Dùng cho **Director + AM** khi bật `PTT_PRESALES_ON_LEAD=1` trên 1 dịch vụ pilot (đề xuất: **AEO** hoặc **SEO Local**).

**Spec:** [2026-07-02-lead-presales-then-lifecycle-design.md](../superpowers/specs/2026-07-02-lead-presales-then-lifecycle-design.md)

---

## Trước khi bật flag

- [ ] Backup DB SQLite production (`cp data/ptt.db data/ptt.db.bak-YYYYMMDD`)
- [ ] Deploy code P1–P4 (rsync / git pull + restart `ptt`)
- [ ] Chạy dry-run backfill lifecycle cũ:
  ```bash
  python3 scripts/backfill_draft_lifecycle_to_presales.py --list-only
  python3 scripts/backfill_draft_lifecycle_to_presales.py --dry-run
  ```
- [ ] Chạy backfill thật (nếu có draft lifecycle trên lead):
  ```bash
  python3 scripts/backfill_draft_lifecycle_to_presales.py --limit 100
  ```
- [ ] Thêm vào `.env`: `PTT_PRESALES_ON_LEAD=1`
- [ ] Restart service Flask / gunicorn

---

## Smoke test (1 lead giả lập)

| # | Bước | Kỳ vọng |
|---|------|---------|
| 1 | `/crm/leads` → mở lead mới | Panel **Pre-sales dịch vụ** hiện; **không** có nút **→ Case/KH** |
| 2 | Chọn slug pilot → **Bắt đầu pre-sales** | 3 tab Lead / Tư vấn / Báo giá + task cards |
| 3 | Intake (gọi hoặc gặp) qua link trên panel | Session `completed`, BANT + decision |
| 4 | Hoàn thành task Lead → **Chuyển bước** Consult | Gate BANT/No-Go hoạt động (confirm nếu Nurture) |
| 5 | **Prefill Consult** | Form Consult có dữ liệu từ Lead/Intake |
| 6 | Hoàn thành Consult + Proposal tasks | Meta: «Chờ ký HĐ → Lifecycle Onboard» |
| 7 | **Tạo HĐ draft** (panel hoặc `/crm/hub`) | HĐ `draft`, KH placeholder `[Lead #…] Chưa ký` |
| 8 | Hub → Sửa HĐ → **Active (ký)** | 1 KH thật + Case; placeholder biến mất |
| 9 | `/crm/service-delivery` | Lifecycle mới ở **Onboard**; **không** thấy deal pre-sales draft |
| 10 | Mở workflow lifecycle | Lead/Consult/Proposal tasks đã ✓; focus Onboard |

---

## Regression nhanh

- [ ] Lead **BĐS** (RE project): `won` + giữ chỗ sản phẩm vẫn qua flow cũ (nếu áp dụng)
- [ ] HĐ **không** gắn `lead_id`: ký vẫn gọi `activate_lifecycle()` legacy
- [ ] `/crm/staff-kpi` — metrics Lead vẫn load
- [ ] Funnel pre-sales trên Service Delivery vẫn có số (cohort lifecycle)

---

## Rollback

1. Tắt `.env`: `PTT_PRESALES_ON_LEAD=0` (hoặc xóa biến)
2. Restart service
3. Lead mới quay lại AI tạo **draft lifecycle** (hành vi cũ)
4. Data presales / lifecycle đã tạo **không** tự xóa — chỉ ngừng luồng mới

---

## Đào tạo AM (15 phút)

1. Pre-sales = **trên Lead**, không mở Service Delivery cho đến khi ký HĐ
2. KH thật + Case chỉ khi HĐ **Active**
3. Intake luôn qua `lead_id` (link trên panel Lead)
4. Director override No-Go → Consult: cần lý do + quyền admin
5. Liên hệ IT nếu ký HĐ báo lỗi «chưa hoàn thành task giai đoạn …»

---

## Sau pilot 2 tuần

- [ ] Thu feedback AM (gate, UI, thiếu field)
- [ ] Quyết định bật flag toàn bộ 12 dịch vụ
- [ ] Cập nhật KPI funnel nếu cần tách presales vs lifecycle (L3+)
