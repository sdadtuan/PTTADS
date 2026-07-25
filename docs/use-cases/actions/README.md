# Chi tiết hành động người dùng — Use Case PTTADS

> **Phiên bản:** 1.0 · **Ngày:** 2026-07-25  
> **Index UC:** [`../README.md`](../README.md) · **Gap analysis:** [`../ACTION-GAP-ANALYSIS.md`](../ACTION-GAP-ANALYSIS.md)

---

## Mục đích

Bổ sung cho mỗi Use Case **toàn bộ bước thao tác** mà người dùng (staff / khách hàng / subscriber) thực hiện trên hệ thống — không chỉ luồng logic.

**Đối tượng đọc:** AM, CSKH, Strategist, QA nghiệm thu, PO kiểm tra coverage nghiệp vụ.

---

## Quy ước bảng hành động

| Cột | Ý nghĩa |
|-----|---------|
| **#** | Thứ tự bước (cùng actor thực hiện tuần tự) |
| **Actor** | Người thực hiện |
| **Màn hình** | URL ops-web / portal-web / public |
| **Thao tác** | Click, nhập, chọn, submit — mô tả cụ thể |
| **Dữ liệu / Input** | Field, file, tham số |
| **Phản hồi hệ thống** | Toast, status, job queued |
| **Gate** | Điều kiện sang bước tiếp (Pass / Fail → nhánh) |

**Ký hiệu Gate:** `✓` bắt buộc pass · `○` optional · `⚠ GAP-xxx` thiếu UI — xem [ACTION-GAP-ANALYSIS.md](../ACTION-GAP-ANALYSIS.md)

---

## Cấu trúc mỗi UC trong file actions

```markdown
### UC-XXX — Tên

**Mục tiêu khách hàng:** …

**Actors:** …

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|

#### Nhánh E1 — …
(bảng bước riêng)

#### Tiêu chí nghiệm thu
- …
```

---

## Danh mục file

| File | Module | UC |
|------|--------|-----|
| [00-SYSTEM-ACTIONS.md](00-SYSTEM-ACTIONS.md) | Cross-system | SYS-001…012 |
| [01-CRM-ACTIONS.md](01-CRM-ACTIONS.md) | CRM Core | CRM-001…015 |
| [02-SVC-ACTIONS.md](02-SVC-ACTIONS.md) | Service Delivery | SVC-001…012 |
| [03-META-ACTIONS.md](03-META-ACTIONS.md) | Meta Enterprise | META-001…014 |
| [04-SEO-ACTIONS.md](04-SEO-ACTIONS.md) | SEO/AEO | SEO-001…014 |
| [05-EM-ACTIONS.md](05-EM-ACTIONS.md) | Email Marketing | EM-001…014 |
| [06-PORTAL-ACTIONS.md](06-PORTAL-ACTIONS.md) | Client Portal | PORTAL-001…010 |
| [07-PLAT-ACTIONS.md](07-PLAT-ACTIONS.md) | Platform | PLAT-001…010 |

---

## Cách dùng khi UAT / đào tạo

1. Chọn UC từ catalog theo vai trò.
2. Chạy **từng dòng bảng** — tick Pass/Fail.
3. Nếu bước có `⚠ GAP` — ghi workaround vào biên bản nghiệm thu.
4. Cross-check với [`handover/06-NGHIEM-THU-VA-BAO-CAO.md`](../../handover/06-NGHIEM-THU-VA-BAO-CAO.md).
