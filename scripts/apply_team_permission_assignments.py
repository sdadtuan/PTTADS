#!/usr/bin/env python3
"""
Gán vai trò CMS + chức vụ CRM cho từng user theo team.

  cd PTT && python3 scripts/apply_team_permission_assignments.py
  cd PTT && python3 scripts/apply_team_permission_assignments.py --dry-run

Ma trận section CRM theo chức vụ đã seed trong crm_position_section_permissions.
Ma trận module CMS theo vai trò đã seed trong cms_role_permissions.
Script này chỉ gán user → (role, position).
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "ptt.db"

# username → (role_code, position_code | None, display_name override | None)
# position_code: CSKH-01 | KD-01 | MKT-01 | MKT-02 | VH-01
TEAM_ASSIGNMENTS: dict[str, tuple[str, str | None, str | None]] = {
    # Quản trị — giữ nguyên, script không ghi đè super_admin / cms_admin
    "admin": ("super_admin", None, None),
    "tuantq": ("cms_admin", None, None),
    # Kinh doanh — sidebar CRM KD, CMS chỉ xem
    "tamnd": ("viewer", "KD-01", "Nguyễn Đình Tâm"),
    "kt-hoaibtn": ("viewer", "KD-01", "Bùi Thị Nhã Hoài"),
    # CSKH — sidebar CSKH + Lead, không Hub/KD/Nhân sự
    "nv.test": ("viewer", "CSKH-01", "NV Test CSKH"),
    # Mẫu Marketing (thêm user CMS khi có nhân viên)
    # "mkt.lead": ("marketing_lead", "MKT-01", "Trưởng phòng Marketing"),
    # "mkt.nv01": ("marketing_staff", "MKT-02", "NV Marketing 01"),
    # Vận hành / HR — nếu cần giới hạn (không dùng cms_admin)
    # "vh.ops": ("viewer", "VH-01", "Điều phối vận hành"),
}


def _position_id(conn: sqlite3.Connection, code: str | None) -> int | None:
    if not code:
        return None
    row = conn.execute(
        "SELECT id FROM crm_positions WHERE lower(trim(code)) = lower(trim(?)) AND active = 1",
        (code,),
    ).fetchone()
    if not row:
        raise ValueError(f"Không tìm thấy chức vụ «{code}»")
    return int(row["id"])


def _staff_display(conn: sqlite3.Connection, username: str) -> str | None:
    row = conn.execute(
        """
        SELECT name FROM crm_staff
        WHERE lower(trim(login_username)) = lower(trim(?)) AND trim(login_username) != ''
        LIMIT 1
        """,
        (username,),
    ).fetchone()
    return str(row["name"]).strip() if row and row["name"] else None


def _staff_password_hash(conn: sqlite3.Connection, username: str) -> str:
    row = conn.execute(
        """
        SELECT password_hash FROM crm_staff
        WHERE lower(trim(login_username)) = lower(trim(?)) AND trim(login_username) != ''
        LIMIT 1
        """,
        (username,),
    ).fetchone()
    return str(row["password_hash"] or "").strip() if row else ""


def apply_assignments(*, dry_run: bool = False) -> int:
    if not DB_PATH.is_file():
        print(f"Không thấy DB: {DB_PATH}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date = ts[:10]
    changed = 0

    for username, (role_code, pos_code, display_override) in TEAM_ASSIGNMENTS.items():
        uname = username.strip()
        if not uname:
            continue

        existing = conn.execute(
            """
            SELECT id, role_code, position_id, display_name
            FROM cms_admin_users
            WHERE lower(trim(username)) = lower(trim(?))
            LIMIT 1
            """,
            (uname,),
        ).fetchone()

        if existing and str(existing["role_code"]) in ("super_admin", "cms_admin"):
            if role_code not in ("super_admin", "cms_admin"):
                print(f"  SKIP {uname}: đang là {existing['role_code']} — không hạ quyền tự động")
                continue
            pos_id = None
        else:
            pos_id = _position_id(conn, pos_code)

        display = display_override or _staff_display(conn, uname) or uname
        pw_hash = _staff_password_hash(conn, uname)

        if existing:
            old_role = str(existing["role_code"])
            old_pos = existing["position_id"]
            if old_role == role_code and (old_pos == pos_id or (old_pos is None and pos_id is None)):
                print(f"  OK   {uname}: đã đúng {role_code}" + (f" + {pos_code}" if pos_code else ""))
                continue
            print(
                f"  UPD  {uname}: {old_role}→{role_code}"
                + (f", chức vụ→{pos_code or '—'}" if pos_code or old_pos else "")
            )
            if not dry_run:
                conn.execute(
                    """
                    UPDATE cms_admin_users
                    SET role_code = ?, position_id = ?, display_name = ?, active = 1, updated_at = ?
                    WHERE id = ?
                    """,
                    (role_code, pos_id, display[:120], ts, int(existing["id"])),
                )
                if pw_hash:
                    conn.execute(
                        """
                        UPDATE cms_admin_users SET password_hash = ?, updated_at = ? WHERE id = ?
                        """,
                        (pw_hash, ts, int(existing["id"])),
                    )
            changed += 1
        else:
            if role_code in ("super_admin", "cms_admin") and uname not in TEAM_ASSIGNMENTS:
                continue
            print(f"  NEW  {uname}: {role_code}" + (f" + {pos_code}" if pos_code else ""))
            if not dry_run:
                conn.execute(
                    """
                    INSERT INTO cms_admin_users (
                        username, display_name, role_code, position_id, password_hash,
                        active, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (uname, display[:120], role_code, pos_id, pw_hash, date, ts),
                )
            changed += 1

    if dry_run:
        print(f"\n(dry-run) Sẽ thay đổi {changed} user.")
        conn.rollback()
    else:
        conn.commit()
        print(f"\nĐã cập nhật {changed} user. Yêu cầu user đăng xuất / đăng nhập lại.")
    conn.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Gán vai trò CMS + chức vụ CRM theo team")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ in thay đổi, không ghi DB")
    args = parser.parse_args()
    print("=== PTT — Gán phân quyền theo team ===\n")
    return apply_assignments(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
