"""DNS verification for sending domains — SPF/DKIM/DMARC (Wave 2)."""
from __future__ import annotations

import logging
import re
import shutil
import subprocess
from typing import Any

logger = logging.getLogger(__name__)

SCHEMA = "email_mkt"


def _dig_txt(name: str) -> list[str]:
    if not shutil.which("dig"):
        return []
    try:
        out = subprocess.run(
            ["dig", "+short", "TXT", name],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if out.returncode != 0:
            return []
        records: list[str] = []
        for line in out.stdout.splitlines():
            text = line.strip().strip('"')
            if text:
                records.append(text)
        return records
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.debug("dig failed for %s: %s", name, exc)
        return []


def verify_domain_dns(domain: str, *, dkim_selector: str = "s1") -> dict[str, Any]:
    domain = domain.strip().lower()
    if not domain or "." not in domain:
        return {"domain": domain, "spf_status": "fail", "dkim_status": "fail", "dmarc_status": "fail"}

    root_txt = _dig_txt(domain)
    spf_status = "pass" if any("v=spf1" in t.lower() for t in root_txt) else "fail"

    dkim_txt = _dig_txt(f"{dkim_selector}._domainkey.{domain}")
    dkim_status = "pass" if dkim_txt else "warn"

    dmarc_txt = _dig_txt(f"_dmarc.{domain}")
    dmarc_status = "pass" if any("v=dmarc1" in t.lower() for t in dmarc_txt) else "warn"
    if dmarc_txt and any(re.search(r"p=none", t, re.I) for t in dmarc_txt):
        dmarc_status = "warn"

    return {
        "domain": domain,
        "spf_status": spf_status,
        "dkim_status": dkim_status,
        "dmarc_status": dmarc_status,
        "records_found": len(root_txt) + len(dkim_txt) + len(dmarc_txt),
    }


def verify_and_persist(domain_id: str, *, actor: str = "system", dkim_selector: str = "s1") -> dict[str, Any]:
    from ptt_jobs.db import pg_connection

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT id::text, client_id::text, domain FROM {SCHEMA}.domains WHERE id = %s::uuid",
                (domain_id,),
            )
            row = cur.fetchone()
            if not row:
                return {"ok": False, "error": "domain_not_found"}
            _, client_id, domain = str(row[0]), str(row[1]), str(row[2])

            result = verify_domain_dns(domain, dkim_selector=dkim_selector)
            status = "active" if result["spf_status"] == "pass" else "pending"
            warm_stage = 1 if result["spf_status"] == "pass" else 0
            cur.execute(
                f"""
                UPDATE {SCHEMA}.domains
                SET spf_status = %s, dkim_status = %s, dmarc_status = %s,
                    last_checked_at = NOW(), status = %s,
                    warm_up_stage = GREATEST(warm_up_stage, %s)
                WHERE id = %s::uuid
                """,
                (
                    result["spf_status"],
                    result["dkim_status"],
                    result["dmarc_status"],
                    status,
                    warm_stage,
                    domain_id,
                ),
            )
            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.audit_log (client_id, actor, action, entity_type, entity_id, after_json)
                VALUES (%s::uuid, %s, 'domain_dns_verified', 'domain', %s::uuid, %s::jsonb)
                """,
                (client_id, actor, domain_id, __import__("json").dumps(result)),
            )
        conn.commit()
    return {"ok": True, "domain_id": domain_id, **result}
