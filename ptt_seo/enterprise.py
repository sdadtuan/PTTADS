"""Enterprise feature flag."""
from __future__ import annotations

import os


def enterprise_enabled() -> bool:
    return os.environ.get("PTT_SEO_ENTERPRISE_ENABLED", "1").strip().lower() not in {
        "0",
        "false",
        "no",
    }
