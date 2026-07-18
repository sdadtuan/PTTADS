# Bộ Test Case CRM — Hướng dẫn tester

**Tải Excel trên hệ thống:** [/crm/test-cases/download.xlsx](/crm/test-cases/download.xlsx)  
**Hoặc:** HDSD → **Tải bộ Test Case (.xlsx)**

## Nội dung file Excel

| Sheet | Mục đích |
|-------|----------|
| **Huong_dan_tester** | Cách điền cột, quy trình test |
| **Flow_Index** | Chỉ mục luồng → sheet test theo module |
| **Test_Cases** | Toàn bộ TC (lifecycle + luồng hệ thống + registry) — **23 cột** |
| **CRM_Lifecycle** | Checklist 26 bước Lead → Retain (kèm gates) |
| **Flow_Nguon_Lead** | Webhook, webform, API, auto-assign |
| **Flow_Service_Delivery** | Kanban workflow, task gate, TMMT |
| **Flow_CSKH** | Case kanban, care report, khách 360 |
| **Flow_Hub_MKT** | HĐ, chiến dịch, SOP, sales pipeline |
| **Flow_Tai_chinh** | KPI alert, RE project, chi phí lifecycle |
| **Flow_Portal** | Báo cáo ngày, KPI NV, payroll |
| **Flow_Product** | Catalog, addon, review queue |
| **Flow_QA** | HDSD + tải bộ test case |
| **Flow_Xu_ly_su_co** | KPI 0, orphan, flag, quyền |
| **Flow_Auth** | Login admin vs portal NV |
| **So_do_*** | Sơ đồ luồng (Lead, Presales gate, Delivery gate, KPI, …) |
| **Hinh_minh_hoa** | Gợi ý chụp màn hình + tên file evidence |
| **Smoke_P0** | Checklist smoke bắt buộc trước release |
| **Tai_khoan_mau** | User/password staging |
| **Tong_quan** | Thống kê |

## Quy trình test đề xuất

1. **Smoke_P0** — pass trước khi test sâu  
2. **CRM_Lifecycle** — luồng chính Lead → Retain  
3. **Flow_*** — theo module phụ trách (xem **Flow_Index**)  
4. **Test_Cases** — regression đầy đủ + ghi Evidence  

## Cột quan trọng (sheet Test_Cases)

- **Hình minh họa** — mô tả ảnh cần chụp  
- **Evidence** — đường dẫn folder ảnh / log  
- **Trạng thái** — dropdown Pass / Fail / Blocked / Skip / Not Run  
- **Sơ đồ tham chiếu** — sheet diagram tương ứng  

## Tài liệu liên quan

- [Hướng dẫn Lead → Retain](./huong-dan-day-du-lead-den-cham-soc-khach-hang.md)  
- [Checklist pilot Pre-sales](./presales-on-lead-pilot-checklist.md)  
- `docs/TEST_CASES_PTT.md` — mô tả chi tiết từng TC  
