import { Injectable } from '@nestjs/common';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import {
  emailJourneysEnabled,
  emailModuleEnabled,
  emailPortalEnabled,
  emailSendEnabled,
  OPS_WEB_EMAIL_ROUTES,
  QA_HANDOFF_CHECKLIST,
} from './email-gate-a.constants';
import {
  EmailGateAReadinessResponse,
  EmailGateASoakSummary,
  EmailGateAStagedStep,
} from './email-gate-a.types';

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
export class EmailGateAService {
  private soakSummary(): EmailGateASoakSummary {
    const skip = (process.env.EM5_SKIP_SOAK ?? '1').trim() === '1';
    const logPath = join(artifactsDir(), 'em5-soak-evidence.jsonl');
    const requiredDays = Number.parseInt(process.env.PTT_EM5_SOAK_DAYS ?? '7', 10) || 7;
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

  private stagedSteps(): EmailGateAStagedStep[] {
    return [
      {
        id: 'B1_ops_admin',
        label: 'Step 1 — Ops admin only',
        enabled: emailModuleEnabled() && !emailSendEnabled(),
        env_keys: ['PTT_EMAIL_ENABLED=1', 'PTT_EMAIL_SEND_ENABLED=0'],
      },
      {
        id: 'B2_send_mvp',
        label: 'Step 2 — Send MVP',
        enabled: emailModuleEnabled() && emailSendEnabled() && !emailPortalEnabled(),
        env_keys: ['PTT_EMAIL_SEND_ENABLED=1'],
      },
      {
        id: 'B3_journeys',
        label: 'Step 3 — Journeys (optional pilot)',
        enabled: emailJourneysEnabled(),
        env_keys: ['PTT_EMAIL_JOURNEYS_ENABLED=1'],
      },
      {
        id: 'B4_portal',
        label: 'Step 4 — Client portal',
        enabled: emailPortalEnabled(),
        env_keys: ['PTT_EMAIL_PORTAL_ENABLED=1'],
      },
    ];
  }

  readiness(): EmailGateAReadinessResponse {
    const art = artifactsDir();
    const waveDir = join(art, 'wave-gates');
    const phase5Report = readJson(join(art, 'phase5-email-pilot-gate-report.json'));
    const handoffReport = readJson(join(waveDir, 'email_handoff_gate_report.json'));
    const soak = this.soakSummary();
    const flags = {
      PTT_EMAIL_ENABLED: emailModuleEnabled(),
      PTT_EMAIL_SEND_ENABLED: emailSendEnabled(),
      PTT_EMAIL_JOURNEYS_ENABLED: emailJourneysEnabled(),
      PTT_EMAIL_PORTAL_ENABLED: emailPortalEnabled(),
    };
    const staged = this.stagedSteps();
    const qaChecklist = QA_HANDOFF_CHECKLIST.map((item) => ({
      id: item.id,
      label: item.label,
      status: item.automated ? ('automated' as const) : ('manual' as const),
    }));
    const notes: string[] = [
      'Staged cutover: Ops admin → Send MVP → Portal → Journeys (never all at once).',
      'Daily soak: ./scripts/phase5_email_soak_record.sh ≥7 days before sign-off.',
      'Full gate pack: ./scripts/email_gate_a_cutover_gate.sh',
    ];
    const automatedOk =
      Boolean(phase5Report?.ok) &&
      (handoffReport ? Boolean(handoffReport.ok) : true) &&
      emailModuleEnabled();
    const ok = automatedOk && soak.ok;
    return {
      ok,
      phase: 'em-5',
      gate: 'A',
      generated_at: new Date().toISOString(),
      flags,
      staged_steps: staged,
      ops_web_routes: [...OPS_WEB_EMAIL_ROUTES],
      soak,
      artifacts: {
        phase5_gate_report: join(art, 'phase5-email-pilot-gate-report.json'),
        handoff_gate_report: join(waveDir, 'email_handoff_gate_report.json'),
        soak_evidence: join(art, 'em5-soak-evidence.jsonl'),
        signoff_template: join(repoRoot(), 'docs/evidence/em5-email-pilot-signoff.template.json'),
      },
      qa_checklist: qaChecklist,
      nginx_redirect: 'deploy/nginx-rs-delivery-admin-retired.conf (/crm/email → /email/hub)',
      notes,
    };
  }

  signoffTemplate(): Record<string, unknown> {
    const path = join(repoRoot(), 'docs/evidence/em5-email-pilot-signoff.template.json');
    return readJson(path) ?? { error: 'template_missing', path };
  }
}
