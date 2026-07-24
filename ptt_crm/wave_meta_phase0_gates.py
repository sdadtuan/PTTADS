"""Wave Meta Phase 0 — hub component extraction gates."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _artifacts_dir() -> Path:
    raw = os.environ.get("PTT_ARTIFACTS_DIR", ".local-dev")
    p = Path(raw)
    return p if p.is_absolute() else ROOT / p


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _check_p0_module_files() -> dict[str, Any]:
    files = [
        ROOT / "services/ops-web/src/lib/meta/types.ts",
        ROOT / "services/ops-web/src/lib/meta/format.ts",
        ROOT / "services/ops-web/src/lib/meta/caps.ts",
        ROOT / "services/ops-web/src/lib/meta/routes.ts",
        ROOT / "services/ops-web/src/components/meta/MetaBadge.tsx",
        ROOT / "services/ops-web/src/components/meta/MetaPageShell.tsx",
        ROOT / "services/ops-web/src/components/meta/MetaHubFilters.tsx",
        ROOT / "services/ops-web/src/components/meta/MetaHubKpiGrid.tsx",
        ROOT / "services/ops-web/src/components/meta/MetaClientTable.tsx",
        ROOT / "services/ops-web/src/components/meta/MetaHubAlertsList.tsx",
        ROOT / "services/ops-web/src/hooks/meta/useMetaHub.ts",
        ROOT / "services/ops-web/src/hooks/meta/useMetaHubAuth.ts",
        ROOT / "services/ops-web/src/components/meta/MetaHubTabPanels.tsx",
        ROOT / "scripts/wave_meta_phase0_gate.sh",
        ROOT / "tests/test_meta_phase0_qa.py",
    ]
    missing = [str(p.relative_to(ROOT)) for p in files if not p.is_file()]
    return {"id": "P0-G01", "ok": not missing, "label": "Phase 0 module files", "missing": missing}


def _check_hub_shell_line_budget() -> dict[str, Any]:
    path = ROOT / "services/ops-web/src/app/meta/facebook-ads/MetaFacebookAdsContent.tsx"
    text = path.read_text(encoding="utf-8")
    lines = len(text.splitlines())
    ok = lines <= 150
    return {
        "id": "P0-G02",
        "ok": ok,
        "label": "MetaFacebookAdsContent shell ≤150 lines",
        "lines": lines,
    }


def _check_hub_uses_extracted_primitives() -> dict[str, Any]:
    text = (ROOT / "services/ops-web/src/app/meta/facebook-ads/MetaFacebookAdsContent.tsx").read_text(
        encoding="utf-8"
    )
    required = (
        "MetaPageShell",
        "MetaHubFilters",
        "MetaHubKpiGrid",
        "MetaHubAlertsList",
        "useMetaHub",
        "MetaHubTabPanels",
    )
    missing = [name for name in required if name not in text]
    forbidden = ("fetchFacebookHub", "staffMe", "fmtVnd")
    leaked = [name for name in forbidden if name in text]
    ok = not missing and not leaked
    return {
        "id": "P0-G03",
        "ok": ok,
        "label": "Hub page composes Phase 0 shell only",
        "missing": missing,
        "leaked_api": leaked,
    }


def _check_ops_css_tokens() -> dict[str, Any]:
    css = (ROOT / "services/ops-web/src/app/globals.css").read_text(encoding="utf-8")
    tokens = (".summary-grid", ".meta-badge", ".meta-badge--ok", ".summary-card")
    missing = [t for t in tokens if t not in css]
    return {"id": "P0-G04", "ok": not missing, "label": "ops-web meta CSS tokens", "missing": missing}


def _check_portal_css_tokens() -> dict[str, Any]:
    css = (ROOT / "services/portal-web/src/app/globals.css").read_text(encoding="utf-8")
    table = (ROOT / "services/portal-web/src/components/PerformanceTable.tsx").read_text(encoding="utf-8")
    tokens = (".channel-badge", ".over-target")
    missing_css = [t for t in tokens if t not in css]
    missing_usage = [t for t in ("channel-badge", "over-target") if t not in table]
    ok = not missing_css and not missing_usage
    return {
        "id": "P0-G05",
        "ok": ok,
        "label": "portal-web channel-badge + over-target",
        "missing_css": missing_css,
        "missing_usage": missing_usage,
    }


def _run_phase0_qa_tests() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_meta_phase0_qa", "-v"],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
    )
    return {
        "id": "P0-G06",
        "ok": proc.returncode == 0,
        "label": "unittest tests.test_meta_phase0_qa",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-800:],
    }


def _run_ops_web_build() -> dict[str, Any]:
    if _truthy("WAVE_META_P0_SKIP_BUILD", "0"):
        return {"id": "P0-G07", "ok": True, "label": "ops-web build (skipped)", "skipped": True}
    ops = ROOT / "services/ops-web"
    proc = subprocess.run(
        ["npm", "run", "build"],
        cwd=str(ops),
        capture_output=True,
        text=True,
    )
    return {
        "id": "P0-G07",
        "ok": proc.returncode == 0,
        "label": "ops-web next build",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-800:],
    }


def _run_portal_web_build() -> dict[str, Any]:
    if _truthy("WAVE_META_P0_SKIP_BUILD", "0"):
        return {"id": "P0-G08", "ok": True, "label": "portal-web build (skipped)", "skipped": True}
    portal = ROOT / "services/portal-web"
    if not (portal / "package.json").is_file():
        return {"id": "P0-G08", "ok": True, "label": "portal-web build (no package)", "skipped": True}
    proc = subprocess.run(
        ["npm", "run", "build"],
        cwd=str(portal),
        capture_output=True,
        text=True,
    )
    return {
        "id": "P0-G08",
        "ok": proc.returncode == 0,
        "label": "portal-web next build",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-800:],
    }


def run_wave_meta_phase0_gates() -> dict[str, Any]:
    checks = [
        _check_p0_module_files(),
        _check_hub_shell_line_budget(),
        _check_hub_uses_extracted_primitives(),
        _check_ops_css_tokens(),
        _check_portal_css_tokens(),
        _run_phase0_qa_tests(),
        _run_ops_web_build(),
        _run_portal_web_build(),
    ]
    ok = all(c.get("ok") for c in checks)
    report = {
        "wave": "meta-phase0",
        "ok": ok,
        "generated_at": _now_iso(),
        "checks": checks,
    }
    out = _artifacts_dir() / "wave-meta-phase0-gate-report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    for check in checks:
        status = "PASS" if check.get("ok") else "FAIL"
        print(f"{status} {check['id']} {check['label']}")
    print(json.dumps({"wave": "meta-phase0", "ok": ok}))
    return report


def main() -> None:
    report = run_wave_meta_phase0_gates()
    raise SystemExit(0 if report.get("ok") else 1)


if __name__ == "__main__":
    main()
