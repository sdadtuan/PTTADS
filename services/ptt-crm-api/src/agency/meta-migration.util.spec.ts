import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import {
  checkAutosyncStandalone,
  evaluateSoakGate,
  writeManualUat,
} from './meta-migration.util';

describe('meta-migration.util', () => {
  const tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'meta-migration-'));

  afterAll(() => {
    fs.rmSync(tmpRoot, { recursive: true, force: true });
  });

  it('checkAutosyncStandalone passes with repo deploy unit and gunicorn off', () => {
    const env = { CRM_FACEBOOK_BACKGROUND_IN_GUNICORN: '0' };
    const status = checkAutosyncStandalone(env);
    expect(status.autosync_unit_present).toBe(true);
    expect(status.autosync_daemon_present).toBe(true);
    expect(status.autosync_gunicorn_background_off).toBe(true);
    expect(status.autosync_unit_no_ptt_dependency).toBe(true);
    expect(status.gate_m1_g07).toBe(true);
  });

  it('evaluateSoakGate returns no_records when log missing', () => {
    const env = {
      PTT_ARTIFACTS_DIR: path.join(tmpRoot, 'empty-artifacts'),
      PTT_HORIZON1_SOAK_LOG: path.join(tmpRoot, 'missing.jsonl'),
    };
    const soak = evaluateSoakGate(env);
    expect(soak.gate_m1_g08).toBe(false);
    expect(soak.soak_error).toBe('no_records');
  });

  it('evaluateSoakGate passes with 7-day span and enough samples', () => {
    const logPath = path.join(tmpRoot, 'soak-pass.jsonl');
    const base = new Date('2026-07-01T06:00:00+00:00');
    const lines: string[] = [];
    for (let i = 0; i < 8; i += 1) {
      const ts = new Date(base.getTime() + i * 86_400_000).toISOString();
      lines.push(JSON.stringify({ recorded_at: ts, ok: true }));
    }
    fs.writeFileSync(logPath, `${lines.join('\n')}\n`, 'utf8');
    const soak = evaluateSoakGate({
      PTT_HORIZON1_SOAK_LOG: logPath,
      PTT_HORIZON1_SOAK_DAYS: '7',
      PTT_HORIZON1_SOAK_MIN_SAMPLES: '7',
    });
    expect(soak.gate_m1_g08).toBe(true);
    expect(soak.soak_7d_ok).toBe(true);
    expect(soak.soak_sample_count).toBe(8);
  });

  it('writeManualUat persists to temp signoff path', () => {
    const signoffPath = path.join(tmpRoot, 'signoff.json');
    const env = { PTT_HORIZON1_SIGNOFF_PATH: signoffPath };
    const out = writeManualUat({ ops_web_hub_cpl_summary: true }, env);
    expect(out.manual_uat.ops_web_hub_cpl_summary).toBe(true);
    const saved = JSON.parse(fs.readFileSync(signoffPath, 'utf8')) as {
      manual_uat: { ops_web_hub_cpl_summary: boolean };
    };
    expect(saved.manual_uat.ops_web_hub_cpl_summary).toBe(true);
  });
});
