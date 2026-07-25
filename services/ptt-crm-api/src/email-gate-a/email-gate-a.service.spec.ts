import { join } from 'node:path';
import { EmailGateAService } from './email-gate-a.service';

describe('EmailGateAService', () => {
  const prev = { ...process.env };

  beforeEach(() => {
    process.env.PTT_REPO_ROOT = join(__dirname, '../../../..');
  });

  afterEach(() => {
    process.env = { ...prev };
  });

  it('readiness returns em-5 gate payload with staged steps', () => {
    process.env.PTT_EMAIL_ENABLED = '1';
    process.env.PTT_EMAIL_SEND_ENABLED = '0';
    process.env.PTT_EMAIL_PORTAL_ENABLED = '0';
    process.env.EM5_SKIP_SOAK = '1';
    const svc = new EmailGateAService();
    const out = svc.readiness();
    expect(out.phase).toBe('em-5');
    expect(out.gate).toBe('A');
    expect(out.flags.PTT_EMAIL_ENABLED).toBe(true);
    expect(out.staged_steps.length).toBeGreaterThanOrEqual(4);
    expect(out.ops_web_routes).toContain('/email/gate-a');
  });

  it('signoffTemplate loads em5 template json', () => {
    const svc = new EmailGateAService();
    const tpl = svc.signoffTemplate();
    expect(tpl).toHaveProperty('phase', 'em-5');
  });
});
