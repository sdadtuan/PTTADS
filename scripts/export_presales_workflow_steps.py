#!/usr/bin/env python3
"""Export SERVICE_WORKFLOW_STEPS (lead/consult/proposal) for Nest presales seed."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from crm_svc_workflow_steps import SERVICE_WORKFLOW_STEPS  # noqa: E402

DEST = ROOT / "services/ptt-crm-api/src/leads-funnel/presales-workflow-steps.data.json"


def main() -> None:
    out: dict[str, dict[str, list]] = {}
    for slug, stages in SERVICE_WORKFLOW_STEPS.items():
        out[slug] = {k: stages.get(k, []) for k in ("lead", "consult", "proposal")}
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    total = sum(len(out[s][st]) for s in out for st in out[s])
    print(f"Wrote {DEST} — {len(out)} services, {total} presales steps")


if __name__ == "__main__":
    main()
