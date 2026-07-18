"""Flask monolith guard — Phase 4 sunset (read-only / retired)."""
from __future__ import annotations

import os
from typing import Any

from flask import jsonify


def _mode() -> str:
    return (os.environ.get("PTT_FLASK_MONOLITH_MODE") or "active").strip().lower()


def flask_monolith_readonly() -> bool:
    return _mode() in {"readonly", "retired"}


def flask_monolith_retired() -> bool:
    return _mode() == "retired"


def deny_flask_write(action: str = "write") -> tuple[Any, int] | None:
    """Return Flask response tuple if mutating requests must be blocked."""
    mode = _mode()
    if mode == "active":
        return None
    if mode == "retired":
        return (
            jsonify(
                {
                    "error": "flask_monolith_retired",
                    "message": "Flask monolith retired — use Nest API",
                    "action": action,
                }
            ),
            503,
        )
    return (
        jsonify(
            {
                "error": "flask_monolith_readonly",
                "message": "Flask monolith read-only — writes via Nest API",
                "action": action,
            }
        ),
        503,
    )
