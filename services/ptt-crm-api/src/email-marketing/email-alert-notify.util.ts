import type { EmailHubAlert } from './email-marketing.types';

const DELIVERABILITY_SEVERITIES = new Set(['warn', 'danger']);

function slackWebhook(): string {
  return (process.env.PTT_EMAIL_SLACK_WEBHOOK ?? process.env.SLACK_WEBHOOK_URL ?? '').trim();
}

function teamsWebhook(): string {
  return (process.env.PTT_EMAIL_TEAMS_WEBHOOK ?? process.env.TEAMS_WEBHOOK_URL ?? '').trim();
}

async function postJson(url: string, text: string): Promise<{ ok: boolean; skipped?: boolean; error?: string }> {
  if (!url) return { ok: false, skipped: true, error: 'webhook_not_configured' };
  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
      signal: AbortSignal.timeout(15000),
    });
    return resp.ok ? { ok: true } : { ok: false, error: `HTTP ${resp.status}` };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) };
  }
}

export async function notifyEmailDeliverabilityAlerts(
  alerts: EmailHubAlert[],
): Promise<{ slack?: Record<string, unknown>; teams?: Record<string, unknown> }> {
  const results: { slack?: Record<string, unknown>; teams?: Record<string, unknown> } = {};
  const targets = alerts.filter(
    (a) =>
      DELIVERABILITY_SEVERITIES.has(a.severity) &&
      (a.message.toLowerCase().includes('complaint') ||
        a.message.toLowerCase().includes('deliverability') ||
        a.message.toLowerCase().includes('domain')),
  );
  if (!targets.length) return results;
  const body = targets.map((a) => `• ${a.message}`).join('\n');
  const text = `:warning: *[Email Marketing]* Deliverability alert\n${body}`;
  if (slackWebhook()) {
    results.slack = await postJson(slackWebhook(), text);
  }
  if (teamsWebhook()) {
    results.teams = await postJson(teamsWebhook(), text.replace(/\*/g, '**'));
  }
  return results;
}
