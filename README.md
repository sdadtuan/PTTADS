# PTT Website Suite

Website landing & CMS cho **PTT Advertising Solutions** (cấu trúc: landing, admin, CMS) với 3 phần:

- `Landing`: giao diện giới thiệu dịch vụ, dự án, tin tức, liên hệ.
- `Admin`: quản trị danh sách dự án và tin tức.
- `CMS`: quản lý nội dung tĩnh (hero, thông tin liên hệ, brand).

## Cấu trúc

```
PTT/
  app.py
  requirements.txt
  templates/
    base.html
    landing.html
    admin.html
    cms.html
  static/
    styles.css
    admin.js
    cms.js
```

## Chạy local

```bash
cd PTT
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Mặc định chạy tại `http://127.0.0.1:5050`.

## Tài liệu

| File | Nội dung |
|------|----------|
| [`docs/SPEC_HE_THONG_PTT.md`](docs/SPEC_HE_THONG_PTT.md) | **Đặc tả hệ thống đầy đủ** (master spec) |
| [`docs/SPEC_UI_UX_PTT.md`](docs/SPEC_UI_UX_PTT.md) | Spec UI/UX & design system |
| [`docs/HUONG_DAN_SU_DUNG_PTT.md`](docs/HUONG_DAN_SU_DUNG_PTT.md) | Hướng dẫn sử dụng |
| [`docs/HE_THONG_PTT.md`](docs/HE_THONG_PTT.md) | Mục lục tóm tắt |
| [`docs/crm/README.md`](docs/crm/README.md) | **CRM Service Delivery** — Lead Intake, Consult Stage, runbooks |

## Route chính

- `/` landing page
- `/admin` dashboard quản trị dữ liệu
- `/cms` trang chỉnh nội dung tĩnh
- `/api/projects` CRUD dự án
- `/api/news` CRUD tin tức
- `/api/settings` đọc/cập nhật cấu hình landing
