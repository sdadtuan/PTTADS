"""Client registry — PostgreSQL agency schema."""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from ptt_jobs.db import PgUnavailableError, pg_connection
from ptt_jobs.events import emit_domain_event

logger = logging.getLogger(__name__)

_CLIENT_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{1,30}$", re.I)


def _row_dict(cur, row) -> dict[str, Any]:
    if row is None:
        return {}
    cols = [d[0] for d in cur.description]
    out: dict[str, Any] = {}
    for idx, col in enumerate(cols):
        val = row[idx]
        if hasattr(val, "isoformat"):
            val = val.isoformat()
        elif val is not None and col == "id":
            val = str(val)
        out[col] = val
    return out


def _strict_onboarding() -> bool:
    return os.environ.get("PTT_CLIENT_STRICT_ONBOARDING", "1").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def list_clients(
    *,
    status: str | None = None,
    q: str | None = None,
    owner_am_id: str | None = None,
    industry_slug: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    clauses = ["1=1"]
    params: list[Any] = []
    if status:
        clauses.append("c.status = %s")
        params.append(status)
    if owner_am_id:
        clauses.append("c.owner_am_id ILIKE %s")
        params.append(f"%{owner_am_id.strip()}%")
    if industry_slug:
        clauses.append("c.industry_slug ILIKE %s")
        params.append(f"%{industry_slug.strip()}%")
    if q:
        clauses.append("(c.code ILIKE %s OR c.name ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])
    params.extend([limit, offset])
    sql = f"""
        SELECT c.id, c.code, c.name, c.industry_slug, c.status, c.owner_am_id,
               c.notes, c.created_at, c.updated_at,
               COALESCE(ch.channels, '') AS channels
        FROM clients c
        LEFT JOIN LATERAL (
            SELECT string_agg(DISTINCT channel, ', ' ORDER BY channel) AS channels
            FROM client_channel_accounts cca
            WHERE cca.client_id = c.id
        ) ch ON TRUE
        WHERE {' AND '.join(clauses)}
        ORDER BY c.updated_at DESC
        LIMIT %s OFFSET %s
    """
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [_row_dict(cur, r) for r in cur.fetchall()]


def fetch_client(client_id: str) -> dict[str, Any] | None:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, code, name, industry_slug, status, owner_am_id, notes, created_at, updated_at
                FROM clients WHERE id = %s::uuid
                """,
                (client_id,),
            )
            row = cur.fetchone()
            return _row_dict(cur, row) if row else None


def fetch_client_by_code(code: str) -> dict[str, Any] | None:
    code_norm = str(code or "").strip().upper()
    if not code_norm:
        return None
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, code, name, industry_slug, status, owner_am_id, notes, created_at, updated_at
                FROM clients WHERE UPPER(code) = %s LIMIT 1
                """,
                (code_norm,),
            )
            row = cur.fetchone()
            return _row_dict(cur, row) if row else None


def create_client(
    *,
    code: str,
    name: str,
    industry_slug: str = "",
    owner_am_id: str = "",
    notes: str = "",
) -> dict[str, Any]:
    code_norm = code.strip().upper()
    if not _CLIENT_CODE_RE.match(code_norm):
        raise ValueError("Mã client 2–31 ký tự: chữ, số, _, -")
    name = name.strip()
    if not name:
        raise ValueError("Thiếu tên client")
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO clients (code, name, industry_slug, status, owner_am_id, notes)
                VALUES (%s, %s, %s, 'onboarding', %s, %s)
                RETURNING id
                """,
                (code_norm, name, industry_slug.strip() or None, owner_am_id or None, notes),
            )
            row = cur.fetchone()
            client_id = str(row[0])
            cur.execute("SELECT seed_client_onboarding(%s::uuid)", (client_id,))
            conn.commit()
    client = fetch_client(client_id)
    assert client
    return client


def update_client(client_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    allowed = {"name", "industry_slug", "owner_am_id", "notes", "status"}
    sets: list[str] = []
    params: list[Any] = []
    for key, val in fields.items():
        if key not in allowed:
            continue
        sets.append(f"{key} = %s")
        params.append(val)
    if not sets:
        client = fetch_client(client_id)
        if not client:
            raise ValueError("Không tìm thấy client")
        return client
    sets.append("updated_at = NOW()")
    params.append(client_id)
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE clients SET {', '.join(sets)} WHERE id = %s::uuid RETURNING id",
                params,
            )
            if not cur.fetchone():
                raise ValueError("Không tìm thấy client")
            conn.commit()
    client = fetch_client(client_id)
    assert client
    return client


def list_onboarding_items(client_id: str) -> list[dict[str, Any]]:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, item_key, label, sort_order, completed, completed_at, completed_by, note
                FROM client_onboarding_items
                WHERE client_id = %s::uuid
                ORDER BY sort_order ASC, item_key ASC
                """,
                (client_id,),
            )
            return [_row_dict(cur, r) for r in cur.fetchall()]


def onboarding_progress(client_id: str) -> dict[str, Any]:
    items = list_onboarding_items(client_id)
    total = len(items)
    done = sum(1 for i in items if i.get("completed"))
    pct = int(round(done / total * 100)) if total else 0
    return {"total": total, "completed": done, "percent": pct}


def set_onboarding_item(
    client_id: str,
    item_key: str,
    *,
    completed: bool,
    completed_by: str = "",
    note: str = "",
) -> dict[str, Any]:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE client_onboarding_items
                SET completed = %s,
                    completed_at = CASE WHEN %s THEN NOW() ELSE NULL END,
                    completed_by = CASE WHEN %s THEN %s ELSE NULL END,
                    note = COALESCE(NULLIF(%s, ''), note)
                WHERE client_id = %s::uuid AND item_key = %s
                RETURNING id
                """,
                (completed, completed, completed, completed_by or None, note, client_id, item_key),
            )
            if not cur.fetchone():
                raise ValueError("Không tìm thấy mục checklist")
            conn.commit()
    items = list_onboarding_items(client_id)
    result = {"items": items, "progress": onboarding_progress(client_id)}
    try:
        from ptt_crm.nest_api import nudge_onboarding_workflow

        nudge_onboarding_workflow(client_id)
    except Exception as exc:
        logger.debug("onboarding nudge skipped: %s", exc)
    return result


def activate_client(client_id: str, *, force: bool = False) -> dict[str, Any]:
    prog = onboarding_progress(client_id)
    if _strict_onboarding() and not force and prog["percent"] < 100:
        raise ValueError(f"Checklist chưa đủ ({prog['completed']}/{prog['total']})")
    client = update_client(client_id, {"status": "active"})
    emit_domain_event(
        "ClientOnboarded",
        "client",
        client_id,
        {"client_id": client_id, "client_code": client.get("code")},
    )
    return client


def list_channel_accounts(client_id: str) -> list[dict[str, Any]]:
    from ptt_agency.channel_vault import public_channel_account, vault_columns_ready

    with pg_connection() as conn:
        with conn.cursor() as cur:
            if vault_columns_ready():
                cur.execute(
                    """
                    SELECT id, channel, external_account_id, display_name, status,
                           credential_ref, access_token_encrypted, token_expires_at,
                           token_status, last_token_refresh_at, created_at, updated_at, meta
                    FROM client_channel_accounts
                    WHERE client_id = %s::uuid
                    ORDER BY channel, external_account_id
                    """,
                    (client_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT id, channel, external_account_id, display_name, status, created_at
                    FROM client_channel_accounts
                    WHERE client_id = %s::uuid
                    ORDER BY channel, external_account_id
                    """,
                    (client_id,),
                )
            rows = [_row_dict(cur, r) for r in cur.fetchall()]
            if vault_columns_ready():
                return [public_channel_account(r) for r in rows]
            return rows


def fetch_channel_account(client_id: str, account_id: str) -> dict[str, Any] | None:
    from ptt_agency.channel_vault import public_channel_account, vault_columns_ready

    with pg_connection() as conn:
        with conn.cursor() as cur:
            if vault_columns_ready():
                cur.execute(
                    """
                    SELECT id, channel, external_account_id, display_name, status,
                           credential_ref, access_token_encrypted, token_expires_at,
                           token_status, last_token_refresh_at, created_at, updated_at, meta
                    FROM client_channel_accounts
                    WHERE client_id = %s::uuid AND id = %s::uuid
                    """,
                    (client_id, account_id),
                )
            else:
                cur.execute(
                    """
                    SELECT id, channel, external_account_id, display_name, status, created_at
                    FROM client_channel_accounts
                    WHERE client_id = %s::uuid AND id = %s::uuid
                    """,
                    (client_id, account_id),
                )
            row = cur.fetchone()
            if not row:
                return None
            data = _row_dict(cur, row)
            return public_channel_account(data) if vault_columns_ready() else data


def add_channel_account(
    client_id: str,
    *,
    channel: str,
    external_account_id: str,
    display_name: str = "",
    access_token: str = "",
    token_expires_at: str | None = None,
    credential_ref: str = "",
    pixel_id: str = "",
) -> dict[str, Any]:
    from ptt_meta.token_vault import normalize_ad_account_id

    ch = channel.strip().lower()
    if ch not in {"meta", "zalo", "google", "email"}:
        raise ValueError("channel không hợp lệ")
    ext = external_account_id.strip()
    if ch == "meta":
        ext = normalize_ad_account_id(ext) or ext
    if not ext:
        raise ValueError("Thiếu external_account_id")
    if not fetch_client(client_id):
        raise ValueError("Không tìm thấy client")

    row = _upsert_channel_account_row(
        client_id,
        channel=ch,
        external_account_id=ext,
        display_name=display_name,
    )
    account_id = str(row["id"])
    if access_token.strip() or credential_ref.strip() or token_expires_at:
        row = set_channel_account_token(
            client_id,
            account_id,
            access_token=access_token,
            token_expires_at=token_expires_at,
            credential_ref=credential_ref,
        )
    else:
        row = fetch_channel_account(client_id, account_id) or row
    if pixel_id.strip():
        row = update_channel_account_meta(client_id, account_id, pixel_id=pixel_id.strip())
    return row


def _upsert_channel_account_row(
    client_id: str,
    *,
    channel: str,
    external_account_id: str,
    display_name: str,
) -> dict[str, Any]:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO client_channel_accounts (
                    client_id, channel, external_account_id, display_name, status
                )
                VALUES (%s::uuid, %s, %s, %s, 'active')
                ON CONFLICT (client_id, channel, external_account_id)
                DO UPDATE SET
                    display_name = COALESCE(NULLIF(EXCLUDED.display_name, ''), client_channel_accounts.display_name),
                    status = 'active',
                    updated_at = NOW()
                RETURNING id, channel, external_account_id, display_name, status
                """,
                (client_id, channel, external_account_id, display_name or None),
            )
            row = cur.fetchone()
            conn.commit()
            return _row_dict(cur, row)


def set_channel_account_token(
    client_id: str,
    account_id: str,
    *,
    access_token: str = "",
    token_expires_at: str | None = None,
    credential_ref: str = "",
    revoke: bool = False,
) -> dict[str, Any]:
    from ptt_agency.channel_vault import compute_token_status, vault_columns_ready
    from ptt_meta.token_crypto import TokenVaultError, encrypt_token, vault_configured

    if not vault_columns_ready():
        raise ValueError("DDL v3 chưa apply — chạy ./scripts/apply_pg_ddl_v3.sh")

    existing = fetch_channel_account(client_id, account_id)
    if not existing:
        raise ValueError("Không tìm thấy channel account")

    enc_blob: bytes | None = None
    cred: str | None = str(credential_ref or "").strip() or None
    expires_dt = None
    if token_expires_at:
        from ptt_agency.channel_vault import _parse_expires

        expires_dt = _parse_expires(token_expires_at)

    if revoke:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE client_channel_accounts
                    SET access_token_encrypted = NULL,
                        credential_ref = NULL,
                        token_status = 'revoked',
                        last_token_refresh_at = NOW(),
                        updated_at = NOW()
                    WHERE client_id = %s::uuid AND id = %s::uuid
                    RETURNING id
                    """,
                    (client_id, account_id),
                )
                if not cur.fetchone():
                    raise ValueError("Không tìm thấy channel account")
                conn.commit()
        out = fetch_channel_account(client_id, account_id)
        assert out
        return out

    if access_token.strip():
        if not vault_configured():
            raise ValueError("PTT_TOKEN_VAULT_KEY chưa cấu hình — không thể lưu token mã hóa")
        try:
            enc_blob = encrypt_token(access_token.strip())
        except TokenVaultError as exc:
            raise ValueError(str(exc)) from exc
    elif not cred:
        raise ValueError("Cần access_token, credential_ref, hoặc revoke=true")

    status = compute_token_status(
        has_token=bool(enc_blob or cred),
        token_status=None,
        token_expires_at=expires_dt,
    )

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE client_channel_accounts
                SET access_token_encrypted = COALESCE(%s, access_token_encrypted),
                    credential_ref = COALESCE(%s, credential_ref),
                    token_expires_at = COALESCE(%s::timestamptz, token_expires_at),
                    token_status = %s,
                    last_token_refresh_at = NOW(),
                    updated_at = NOW()
                WHERE client_id = %s::uuid AND id = %s::uuid
                RETURNING id
                """,
                (
                    enc_blob,
                    cred,
                    token_expires_at,
                    status,
                    client_id,
                    account_id,
                ),
            )
            if not cur.fetchone():
                raise ValueError("Không tìm thấy channel account")
            conn.commit()

    out = fetch_channel_account(client_id, account_id)
    assert out
    return out


def update_channel_account_meta(
    client_id: str,
    account_id: str,
    *,
    pixel_id: str | None = None,
    meta_patch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge JSONB meta on channel account (e.g. pixel_id for CAPI / closed-loop)."""
    from ptt_agency.channel_vault import vault_columns_ready

    if not vault_columns_ready():
        raise ValueError("DDL v3 chưa apply — chạy ./scripts/apply_pg_ddl_v3.sh")

    patch: dict[str, Any] = dict(meta_patch or {})
    if pixel_id is not None:
        pid = str(pixel_id).strip()
        if pid:
            patch["pixel_id"] = pid
        elif "pixel_id" in patch:
            patch["pixel_id"] = ""

    if not patch:
        out = fetch_channel_account(client_id, account_id)
        if not out:
            raise ValueError("Không tìm thấy channel account")
        return out

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT meta FROM client_channel_accounts
                WHERE client_id = %s::uuid AND id = %s::uuid
                """,
                (client_id, account_id),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("Không tìm thấy channel account")
            current = row[0] if isinstance(row[0], dict) else {}
            if not isinstance(current, dict):
                current = {}
            merged = {**current, **patch}
            if pixel_id is not None and not str(pixel_id).strip():
                merged.pop("pixel_id", None)
            cur.execute(
                """
                UPDATE client_channel_accounts
                SET meta = %s::jsonb, updated_at = NOW()
                WHERE client_id = %s::uuid AND id = %s::uuid
                RETURNING id
                """,
                (json.dumps(merged), client_id, account_id),
            )
            if not cur.fetchone():
                raise ValueError("Không tìm thấy channel account")
            conn.commit()

    out = fetch_channel_account(client_id, account_id)
    assert out
    return out


def load_channel_account_for_sync(
    client_id: str | None = None,
    *,
    channel: str = "meta",
) -> list[dict[str, Any]]:
    """Internal — includes encrypted blob for insights sync (never expose via API)."""
    from ptt_agency.channel_vault import vault_columns_ready

    if not vault_columns_ready():
        return []

    ch = (channel or "meta").strip().lower()
    with pg_connection() as conn:
        with conn.cursor() as cur:
            if client_id:
                cur.execute(
                    """
                    SELECT id, client_id, channel, external_account_id, display_name,
                           credential_ref, access_token_encrypted, meta, token_status, status
                    FROM client_channel_accounts
                    WHERE channel = %s AND status = 'active' AND client_id = %s::uuid
                    ORDER BY external_account_id
                    """,
                    (ch, client_id),
                )
            else:
                cur.execute(
                    """
                    SELECT id, client_id, channel, external_account_id, display_name,
                           credential_ref, access_token_encrypted, meta, token_status, status
                    FROM client_channel_accounts
                    WHERE channel = %s AND status = 'active'
                    ORDER BY client_id, external_account_id
                    """,
                    (ch,),
                )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def list_kpi_definitions() -> list[dict[str, Any]]:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT code, name, formula, granularity, description
                FROM kpi_definitions ORDER BY code
                """
            )
            return [_row_dict(cur, r) for r in cur.fetchall()]


def pg_ready() -> bool:
    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True
    except Exception:
        return False


def client_counts() -> dict[str, int]:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status, COUNT(*)::int FROM clients GROUP BY status")
            return {str(r[0]): int(r[1]) for r in cur.fetchall()}
