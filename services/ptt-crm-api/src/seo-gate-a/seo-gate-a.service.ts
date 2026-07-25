import { Injectable } from '@nestjs/common';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import {
  experimentsEnabled,
  governanceEnabled,
  OPS_WEB_SEO_ROUTES,
  portalSeoEnabled,
  QA_HANDOFF_CHECKLIST,
} from './seo-gate-a.constants';
import {
  SeoGateAReadinessResponse,
  SeoGateASoakSummary,
  SeoGateAStagedStep,
} from './seo-gate-a.types';

function repoRoot(): string {
  return process.env.PTT_REPO_ROOT?.trim() || process.cwd();
}

function artifactsDir(): string {
  const raw = (process.env.PTT_ARTIFACTS_DIR ?? '.local-dev').trim();
  return raw.startsWith('/') ? raw : join(repoRoot(), raw);
}

function readJson(path: string): Record<string, unknown> | null {
  if (!existsSync(path)) return null;
  try {
    return JSON.parse(readFileSync(path, 'utf8')) as Record<string, unknown>;
  } catch {
    return null;
  }
}

@Injectable()
export class SeoGateAService {
  private soakSummary(): SeoGateASoakSummary {
    const skip = (process.env.PHASE5_SKIP_SOAK ?? '1').trim() === '1';
    const logPath = join(artifactsDir(), 'phase5-soak-evidence.jsonl');
    const requiredDays = Number.parseInt(process.env.PTT_PHASE5_SOAK_DAYS ?? '7', 10) || 7;
    if (skip) {
      return {
        ok: true,
        skipped: true,
        required_days: requiredDays,
        sample_count: 0,
        span_days: null,
        failure_count: 0,
        log_path: logPath,
      };
    }
    if (!existsSync(logPath)) {
      return {
        ok: false,
        required_days: requiredDays,
        sample_count: 0,
        span_days: null,
        failure_count: 0,
        log_path: logPath,
      };
    }
    const lines = readFileSync(logPath, 'utf8')
      .split('\n')
      .map((l) => l.trim())
      .filter(Boolean);
    let failureCount = 0;
    const dates: Date[] = [];
    for (const line of lines) {
      try {
        const row = JSON.parse(line) as Record<string, unknown>;
        if (row.ok === false) failureCount += 1;
        const ts = String(row.recorded_at ?? '');
        const d = new Date(ts);
        if (!Number.isNaN(d.getTime())) dates.push(d);
      } catch {
        failureCount += 1;
      }
    }
    let spanDays: number | null = null;
    if (dates.length >= 2) {
      dates.sort((a, b) => a.getTime() - b.getTime());
      spanDays = Math.floor((dates[dates.length - 1].getTime() - dates[0].getTime()) / 86400000);
    }
    const sampleCount = lines.length;
    const ok = sampleCount >= requiredDays && failureCount === 0 && (spanDays ?? 0) >= requiredDays - 1;
    return {
      ok,
      required_days: requiredDays,
      sample_count: sampleCount,
      span_days: spanDays,
      failure_count: failureCount,
      log_path: logPath,
    };
  }

  private stagedSteps(): SeoGateAStagedStep[] {
    return [
      {
        id: 'B1_governance',
        label: 'Step 1 — Governance ON',
        enabled: governanceEnabled(),
        env_keys: ['PTT_SEO_GOVERNANCE_ENABLED=1'],
      },
      {
        id: 'B2_portal',
        label: 'Step 2 — Portal SEO ON',
        enabled: portalSeoEnabled(),
        env_keys: ['PTT_PORTAL_SEO_ENABLED=1', 'PTT_PORTAL_SEO_SERVICE_TOKEN'],
      },
      {
        id: 'B3_experiments',
        label: 'Step 3 — Experiments ON',
        enabled: experimentsEnabled(),
        env_keys: ['PTT_SEO_EXPERIMENTS_ENABLED=1'],
      },
    ];
  }

  readiness(): SeoGateAReadinessResponse {
    const art = artifactsDir();
    const waveDir = join(art, 'wave-gates');
    const phase5Report = readJson(join(art, 'phase5-gate-report.json'));
    const portalSignoff = readJson(join(art, 'phase5-portal-seo-uat-signoff.json'));
    const b6Report = readJson(join(waveDir, 'seo_b6_gate_report.json'));
    const soak = this.soakSummary();
    const flags = {
      PTT_SEO_GOVERNANCE_ENABLED: governanceEnabled(),
      PTT_PORTAL_SEO_ENABLED: portalSeoEnabled(),
      PTT_SEO_EXPERIMENTS_ENABLED: experimentsEnabled(),
    };
    const staged = this.stagedSteps();
    const qaChecklist = QA_HANDOFF_CHECKLIST.map((item) => ({
      id: item.id,
      label: item.label,
      status: item.automated ? ('automated' as const) : ('manual' as const),
    }));
    const notes: string[] = [
      'Staged cutover: Governance → Portal → Experiments (never all at once).',
      'Daily soak: ./scripts/phase5_soak_record.sh ≥7 days before sign-off.',
      'Full gate pack: ./scripts/seo_gate_a_cutover_gate.sh',
    ];
    const automatedOk =
      Boolean(phase5Report?.ok) &&
      Boolean(b6Report?.ok) &&
      (portalSeoEnabled() ? Boolean(portalSignoff?.playwright_e2e) : true);
    const ok = automatedOk && soak.ok && governanceEnabled();
    return {
      ok,
      phase: '7',
      gate: 'A',
      generated_at: new Date().toISOString(),
      flags,
      staged_steps: staged,
      ops_web_routes: [...OPS_WEB_SEO_ROUTES],
      soak,
      artifacts: {
        phase5_gate_report: join(art, 'phase5-gate-report.json'),
        portal_uat_signoff: join(art, 'phase5-portal-seo-uat-signoff.json'),
        soak_evidence: join(art, 'phase5-soak-evidence.jsonl'),
        seo_b6_gate_report: join(waveDir, 'seo_b6_gate_report.json'),
        signoff_template: join(repoRoot(), 'docs/evidence/seo-gate-a-signoff.template.json'),
      },
      qa_checklist: qaChecklist,
      nginx_redirect: 'deploy/nginx-seo-gate-a-redirect.conf',
      notes,
    };
  }

  signoffTemplate(): Record<string, unknown> {
    const path = join(repoRoot(), 'docs/evidence/seo-gate-a-signoff.template.json');
    return readJson(path) ?? { error: 'template_missing', path };
  }
}
