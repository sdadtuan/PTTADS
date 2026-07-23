import * as fs from 'fs';
import * as path from 'path';

export const MANUAL_UAT_FIELDS = [
  'ops_web_hub_cpl_summary',
  'webhook_test_lead_created',
  'autosync_single_process',
  'portal_meta_readonly',
  'campaign_write_approve_smoke',
] as const;

export type ManualUatField = (typeof MANUAL_UAT_FIELDS)[number];

export type ManualUatState = Record<ManualUatField, boolean>;

export interface AutosyncGateStatus {
  gate_m1_g07: boolean;
  autosync_standalone_ok: boolean;
  autosync_unit_present: boolean;
  autosync_daemon_present: boolean;
  autosync_gunicorn_background_off: boolean;
  autosync_unit_no_ptt_dependency: boolean;
}

export interface SoakGateStatus {
  gate_m1_g08: boolean;
  soak_7d_ok: boolean;
  soak_span_days: number | null;
  soak_sample_count: number;
  soak_required_days: number;
  soak_min_samples: number;
  soak_failure_count: number;
  soak_latest_recorded_at: string | null;
  soak_error: string | null;
}

export function repoRoot(): string {
  return path.resolve(process.cwd(), '../..');
}

export function artifactsDir(env: NodeJS.ProcessEnv = process.env): string {
  const raw = (env.PTT_ARTIFACTS_DIR ?? '.local-dev').trim() || '.local-dev';
  return path.isAbsolute(raw) ? raw : path.join(repoRoot(), raw);
}

export function signoffEvidencePath(env: NodeJS.ProcessEnv = process.env): string {
  const override = (env.PTT_HORIZON1_SIGNOFF_PATH ?? '').trim();
  if (override) {
    return path.isAbsolute(override) ? override : path.join(repoRoot(), override);
  }
  return path.join(repoRoot(), 'docs/evidence/horizon1-meta-ads-signoff.json');
}

export function signoffTemplatePath(): string {
  return path.join(repoRoot(), 'docs/evidence/horizon1-meta-ads-signoff.template.json');
}

function isEnvTruthy(env: NodeJS.ProcessEnv, name: string, defaultValue = '0'): boolean {
  return ['1', 'true', 'yes', 'on'].includes((env[name] ?? defaultValue).trim().toLowerCase());
}

function parseIsoTs(value: unknown): Date | null {
  if (typeof value !== 'string' || !value.trim()) return null;
  let text = value.trim();
  if (text.endsWith('Z')) text = `${text.slice(0, -1)}+00:00`;
  const dt = new Date(text);
  return Number.isNaN(dt.getTime()) ? null : dt;
}

export function defaultManualUat(): ManualUatState {
  return {
    ops_web_hub_cpl_summary: false,
    webhook_test_lead_created: false,
    autosync_single_process: false,
    portal_meta_readonly: false,
    campaign_write_approve_smoke: false,
  };
}

export function readMigrationSignoff(env: NodeJS.ProcessEnv = process.env): {
  ok: boolean;
  path: string;
  manual_uat: ManualUatState;
  updated_at: string | null;
  signed_at: string | null;
  created_from_template: boolean;
} {
  const target = signoffEvidencePath(env);
  let createdFromTemplate = false;
  let raw: Record<string, unknown> = {};
  if (!fs.existsSync(target)) {
    const templatePath = signoffTemplatePath();
    if (fs.existsSync(templatePath)) {
      raw = JSON.parse(fs.readFileSync(templatePath, 'utf8')) as Record<string, unknown>;
      createdFromTemplate = true;
    }
  } else {
    raw = JSON.parse(fs.readFileSync(target, 'utf8')) as Record<string, unknown>;
  }
  const manualRaw = (raw.manual_uat ?? {}) as Record<string, unknown>;
  const manual_uat = defaultManualUat();
  for (const field of MANUAL_UAT_FIELDS) {
    manual_uat[field] = manualRaw[field] === true;
  }
  return {
    ok: true,
    path: path.relative(repoRoot(), target) || target,
    manual_uat,
    updated_at: typeof raw.updated_at === 'string' ? raw.updated_at : null,
    signed_at: typeof raw.signed_at === 'string' ? raw.signed_at : null,
    created_from_template: createdFromTemplate,
  };
}

export function writeManualUat(
  updates: Partial<ManualUatState>,
  env: NodeJS.ProcessEnv = process.env,
): {
  ok: boolean;
  path: string;
  manual_uat: ManualUatState;
  updated_at: string;
} {
  const target = signoffEvidencePath(env);
  let raw: Record<string, unknown> = {};
  if (fs.existsSync(target)) {
    raw = JSON.parse(fs.readFileSync(target, 'utf8')) as Record<string, unknown>;
  } else {
    const templatePath = signoffTemplatePath();
    if (!fs.existsSync(templatePath)) {
      throw new Error('signoff_template_missing');
    }
    raw = JSON.parse(fs.readFileSync(templatePath, 'utf8')) as Record<string, unknown>;
  }
  const manualRaw = { ...defaultManualUat(), ...((raw.manual_uat ?? {}) as Record<string, unknown>) };
  for (const field of MANUAL_UAT_FIELDS) {
    if (typeof updates[field] === 'boolean') {
      manualRaw[field] = updates[field];
    }
  }
  const manual_uat = defaultManualUat();
  for (const field of MANUAL_UAT_FIELDS) {
    manual_uat[field] = manualRaw[field] === true;
  }
  const updatedAt = new Date().toISOString();
  raw.manual_uat = manual_uat;
  raw.updated_at = updatedAt;
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, `${JSON.stringify(raw, null, 2)}\n`, 'utf8');
  return {
    ok: true,
    path: path.relative(repoRoot(), target) || target,
    manual_uat,
    updated_at: updatedAt,
  };
}

export function checkAutosyncStandalone(env: NodeJS.ProcessEnv = process.env): AutosyncGateStatus {
  const root = repoRoot();
  const unitPath = path.join(root, 'deploy/ptt-fb-autosync.service');
  const daemonPath = path.join(root, 'scripts/run_fb_autosync_daemon.py');
  const crmSqlitePath = path.join(root, 'ptt_crm/crm_sqlite.py');
  const unitPresent = fs.existsSync(unitPath);
  const daemonPresent = fs.existsSync(daemonPath);
  const crmSqlitePresent = fs.existsSync(crmSqlitePath);
  const gunicornOff = !isEnvTruthy(env, 'CRM_FACEBOOK_BACKGROUND_IN_GUNICORN', '0');
  let noPttDependency = false;
  if (unitPresent) {
    const unitText = fs.readFileSync(unitPath, 'utf8');
    noPttDependency = !unitText.includes('Wants=ptt.service');
  }
  const ok =
    unitPresent && daemonPresent && crmSqlitePresent && gunicornOff && noPttDependency;
  return {
    gate_m1_g07: ok,
    autosync_standalone_ok: ok,
    autosync_unit_present: unitPresent,
    autosync_daemon_present: daemonPresent,
    autosync_gunicorn_background_off: gunicornOff,
    autosync_unit_no_ptt_dependency: noPttDependency,
  };
}

export function evaluateSoakGate(env: NodeJS.ProcessEnv = process.env): SoakGateStatus {
  const requiredDays = Number(env.PTT_HORIZON1_SOAK_DAYS ?? '7') || 7;
  const minSamples = Number(env.PTT_HORIZON1_SOAK_MIN_SAMPLES ?? '7') || 7;
  const soakLogOverride = (env.PTT_HORIZON1_SOAK_LOG ?? '').trim();
  const logPath = soakLogOverride
    ? path.isAbsolute(soakLogOverride)
      ? soakLogOverride
      : path.join(repoRoot(), soakLogOverride)
    : path.join(artifactsDir(env), 'horizon1-meta-ads-soak-evidence.jsonl');

  if (!fs.existsSync(logPath)) {
    return {
      gate_m1_g08: false,
      soak_7d_ok: false,
      soak_span_days: null,
      soak_sample_count: 0,
      soak_required_days: requiredDays,
      soak_min_samples: minSamples,
      soak_failure_count: 0,
      soak_latest_recorded_at: null,
      soak_error: 'no_records',
    };
  }

  const lines = fs.readFileSync(logPath, 'utf8').split('\n');
  const records: Record<string, unknown>[] = [];
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    try {
      records.push(JSON.parse(trimmed) as Record<string, unknown>);
    } catch {
      // skip invalid line
    }
  }

  if (!records.length) {
    return {
      gate_m1_g08: false,
      soak_7d_ok: false,
      soak_span_days: null,
      soak_sample_count: 0,
      soak_required_days: requiredDays,
      soak_min_samples: minSamples,
      soak_failure_count: 0,
      soak_latest_recorded_at: null,
      soak_error: 'no_records',
    };
  }

  const timestamps = records
    .map((row) => parseIsoTs(row.recorded_at))
    .filter((ts): ts is Date => ts !== null);
  if (!timestamps.length) {
    return {
      gate_m1_g08: false,
      soak_7d_ok: false,
      soak_span_days: null,
      soak_sample_count: records.length,
      soak_required_days: requiredDays,
      soak_min_samples: minSamples,
      soak_failure_count: records.filter((row) => row.ok !== true).length,
      soak_latest_recorded_at: null,
      soak_error: 'invalid_timestamps',
    };
  }

  const minTs = Math.min(...timestamps.map((ts) => ts.getTime()));
  const maxTs = Math.max(...timestamps.map((ts) => ts.getTime()));
  const spanDays = (maxTs - minTs) / 86_400_000;
  const failures = records.filter((row) => row.ok !== true);
  const ok = spanDays >= requiredDays && records.length >= minSamples && failures.length === 0;
  const latest = records[records.length - 1];
  return {
    gate_m1_g08: ok,
    soak_7d_ok: ok,
    soak_span_days: Math.round(spanDays * 100) / 100,
    soak_sample_count: records.length,
    soak_required_days: requiredDays,
    soak_min_samples: minSamples,
    soak_failure_count: failures.length,
    soak_latest_recorded_at:
      typeof latest?.recorded_at === 'string' ? latest.recorded_at : null,
    soak_error: ok ? null : failures.length ? 'failures_present' : 'insufficient_span_or_samples',
  };
}
