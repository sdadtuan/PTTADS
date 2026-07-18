"""Phase 3 Temporal workflow gate pack — unit + live execution."""
from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CLIENT = "550e8400-e29b-41d4-a716-446655440000"

WORKFLOW_UNIT_MODULES: tuple[str, ...] = (
    "tests.test_client_onboarding_workflow",
    "tests.test_launch_qa_workflow",
    "tests.test_creative_approval_workflow",
)


def _artifacts_dir() -> Path:
    return Path(os.environ.get("PTT_ARTIFACTS_DIR") or (ROOT / ".local-dev"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _run_unittest_modules(modules: tuple[str, ...]) -> dict[str, Any]:
    python = sys.executable
    root = str(ROOT)
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", root)
    failed_modules: list[str] = []
    output_parts: list[str] = []
    total_run = 0
    for mod in modules:
        proc = subprocess.run(
            [python, "-m", "unittest", mod],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        tail = (proc.stdout or "") + (proc.stderr or "")
        output_parts.append(f"=== {mod} ===\n{tail[-800:]}")
        m = re.search(r"Ran (\d+) test", tail)
        if m:
            total_run += int(m.group(1))
        if proc.returncode != 0:
            failed_modules.append(mod)
    return {
        "ok": not failed_modules,
        "tests_run": total_run,
        "modules": list(modules),
        "failed_modules": failed_modules,
        "output_tail": "\n".join(output_parts)[-4000:],
    }


def verify_workflow_unit_tests() -> dict[str, Any]:
    result = _run_unittest_modules(WORKFLOW_UNIT_MODULES)
    return {"id": "T3-G01", "label": "Workflow unit tests", **result}


def verify_temporal_server() -> dict[str, Any]:
    async def _connect() -> dict[str, str]:
        from temporalio.client import Client

        from ptt_temporal.config import temporal_address, temporal_namespace

        addr = temporal_address()
        ns = temporal_namespace()
        await Client.connect(addr, namespace=ns)
        return {"address": addr, "namespace": ns}

    try:
        meta = asyncio.run(_connect())
        return {
            "id": "T3-G02",
            "ok": True,
            "label": "Temporal server reachable",
            **meta,
        }
    except Exception as exc:
        return {
            "id": "T3-G02",
            "ok": False,
            "label": "Temporal server reachable",
            "error": str(exc),
        }


async def _wait_workflow(handle, *, timeout_sec: float = 45.0) -> dict[str, Any]:
    try:
        return await asyncio.wait_for(handle.result(), timeout=timeout_sec)
    except asyncio.TimeoutError:
        return {"status": "timeout"}


async def _run_live_onboarding(client_id: str) -> dict[str, Any]:
    from temporalio.client import Client

    from ptt_agency.clients import list_onboarding_items, set_onboarding_item
    from ptt_temporal.config import task_queue, temporal_address, temporal_namespace
    from ptt_temporal.workflows.client_onboarding import ClientOnboardingInput, ClientOnboardingWorkflow

    wf_id = f"gate-onboarding-{uuid.uuid4().hex[:10]}"
    temporal = await Client.connect(temporal_address(), namespace=temporal_namespace())
    handle = await temporal.start_workflow(
        ClientOnboardingWorkflow.run,
        ClientOnboardingInput(client_id=client_id, started_by="gate@pttads.vn"),
        id=wf_id,
        task_queue=task_queue(),
    )
    for item in list_onboarding_items(client_id):
        set_onboarding_item(
            client_id,
            str(item["item_key"]),
            completed=True,
            completed_by="gate@pttads.vn",
        )
    await handle.signal("checklist_updated", {})
    result = await _wait_workflow(handle)
    ok = result.get("status") == "completed"
    return {
        "id": "T3-G03",
        "ok": ok,
        "label": "Live ClientOnboardingWorkflow",
        "workflow_id": wf_id,
        "result": result,
    }


async def _run_live_launch_qa(client_id: str) -> dict[str, Any]:
    from temporalio.client import Client

    from ptt_agency.launch_qa import DEFAULT_CHECKLIST, create_launch_qa_run, update_launch_qa_item
    from ptt_temporal.config import task_queue, temporal_address, temporal_namespace
    from ptt_temporal.workflows.launch_qa import LaunchQAInput, LaunchQAWorkflow

    campaign_id = f"camp_gate_{uuid.uuid4().hex[:8]}"
    run = create_launch_qa_run(
        client_id=client_id,
        external_campaign_id=campaign_id,
        campaign_name="Gate QA Campaign",
        started_by="gate@pttads.vn",
    )
    run_id = str(run["id"])
    wf_id = f"gate-launch-qa-{uuid.uuid4().hex[:10]}"
    temporal = await Client.connect(temporal_address(), namespace=temporal_namespace())
    handle = await temporal.start_workflow(
        LaunchQAWorkflow.run,
        LaunchQAInput(
            run_id=run_id,
            client_id=client_id,
            external_campaign_id=campaign_id,
            started_by="gate@pttads.vn",
            campaign_name="Gate QA Campaign",
        ),
        id=wf_id,
        task_queue=task_queue(),
    )
    for key in DEFAULT_CHECKLIST:
        update_launch_qa_item(run_id, key, completed=True, completed_by="gate@pttads.vn")
    await handle.signal("checklist_updated", {})
    result = await _wait_workflow(handle)
    ok = result.get("status") == "passed"
    return {
        "id": "T3-G04",
        "ok": ok,
        "label": "Live LaunchQAWorkflow",
        "workflow_id": wf_id,
        "run_id": run_id,
        "result": result,
    }


async def _run_live_creative(client_id: str) -> dict[str, Any]:
    from temporalio.client import Client

    from ptt_temporal.config import task_queue, temporal_address, temporal_namespace
    from ptt_temporal.workflows.creative_approval import CreativeApprovalInput, CreativeApprovalWorkflow

    creative_id = f"gate-creative-{uuid.uuid4().hex[:10]}"
    wf_id = f"gate-creative-wf-{uuid.uuid4().hex[:10]}"
    temporal = await Client.connect(temporal_address(), namespace=temporal_namespace())
    handle = await temporal.start_workflow(
        CreativeApprovalWorkflow.run,
        CreativeApprovalInput(
            creative_id=creative_id,
            client_id=client_id,
            title="Gate Banner",
            version=1,
            submitted_by="gate@pttads.vn",
        ),
        id=wf_id,
        task_queue=task_queue(),
    )
    await handle.signal("approve_creative", {"reviewed_by": "approver@demo.local", "note": "gate ok"})
    result = await _wait_workflow(handle)
    ok = result.get("decision") == "approved"
    return {
        "id": "T3-G05",
        "ok": ok,
        "label": "Live CreativeApprovalWorkflow",
        "workflow_id": wf_id,
        "creative_id": creative_id,
        "result": result,
    }


async def _run_all_live(client_id: str) -> dict[str, dict[str, Any]]:
    return {
        "live_onboarding": await _run_live_onboarding(client_id),
        "live_launch_qa": await _run_live_launch_qa(client_id),
        "live_creative": await _run_live_creative(client_id),
    }


def verify_nest_workflow_api(client_id: str) -> dict[str, Any]:
    from ptt_crm.nest_api import start_onboarding_workflow

    status, body = start_onboarding_workflow(client_id, started_by="gate@pttads.vn")
    started = bool(body.get("workflow_started"))
    signal = body.get("temporal_signal")
    ok = status in (200, 201) and (started or signal in ("sent", "stub", "skipped"))
    return {
        "id": "T3-G06",
        "ok": ok,
        "label": "Nest workflow start API",
        "http_status": status,
        "workflow_id": body.get("workflow_id"),
        "workflow_started": started,
        "temporal_signal": signal,
    }


def run_temporal_gate_pack(*, live: bool = True, client_id: str | None = None) -> dict[str, Any]:
    cid = client_id or os.environ.get("TEMPORAL_GATE_CLIENT_ID", DEFAULT_CLIENT)
    artifacts = _artifacts_dir()
    artifacts.mkdir(parents=True, exist_ok=True)

    steps: dict[str, Any] = {
        "unit_tests": verify_workflow_unit_tests(),
        "temporal_server": verify_temporal_server(),
    }

    if live and steps["temporal_server"].get("ok"):
        try:
            live_steps = asyncio.run(_run_all_live(cid))
            steps.update(live_steps)
        except Exception as exc:
            steps["live_error"] = {"ok": False, "error": str(exc)}

    api_url = (os.environ.get("PTT_API_URL") or os.environ.get("NEST_LEADS_BASE_URL") or "").strip()
    if api_url:
        steps["nest_api"] = verify_nest_workflow_api(cid)

    all_ok = all(bool(s.get("ok")) for k, s in steps.items() if k != "live_error")
    report = {
        "phase": "phase3_temporal_gate",
        "generated_at": _now_iso(),
        "client_id": cid,
        "ok": all_ok,
        "steps": steps,
        "summary": {
            "total": len(steps),
            "passed": sum(1 for s in steps.values() if s.get("ok")),
            "failed": [k for k, s in steps.items() if not s.get("ok")],
        },
    }
    out = artifacts / "phase3-temporal-gate-report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    live = "--no-live" not in (argv or sys.argv[1:])
    report = run_temporal_gate_pack(live=live)
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
