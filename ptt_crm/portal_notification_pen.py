"""Portal notification tenant scope helper — PROD-H-PEN."""
from __future__ import annotations


def assert_client_scoped(*, user_client_id: str, requested_client_id: str) -> dict[str, object]:
    """Mirror PortalNotificationService.assertClient — JWT client_id is authoritative."""
    if not user_client_id:
        return {"allowed": False, "reason": "missing_client_id"}
    if user_client_id != requested_client_id:
        return {"allowed": False, "reason": "client_mismatch"}
    return {"allowed": True, "reason": "ok"}
