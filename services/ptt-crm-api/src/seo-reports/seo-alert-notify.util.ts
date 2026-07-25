const SLACK_ALERT_TYPES = new Set([
  'critical_issues',
  'report_schedule_failed',
  'sync_failed',
  'freshness_urgent',
  'aeo_coverage_low',
  'content_overdue',
  'crawl_stale',
]);

const PREFIX: Record<string, string> = {
  critical_issues: ':rotating_light:',
  report_schedule_failed: ':warning:',
  sync_failed: ':warning:',
  freshness_urgent: ':fire:',
  aeo_coverage_low: ':chart_with_downwards_trend:',
  content_overdue: ':hourglass:',
  crawl_stale: ':spider_web:',
};

function slackWebhook(): string {
  return (process.env.PTT_SEO_SLACK_WEBHOOK ?? process.env.SLACK_WEBHOOK_URL ?? '').trim();
}

function teamsWebhook(): string {
  return (process.env.PTT_SEO_TEAMS_WEBHOOK ?? process.env.TEAMS_WEBHOOK_URL ?? '').trim();
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

export async function notifySeoAlert(params: {
  alertType: string;
  message: string;
  link?: string;
}): Promise<{ slack?: Record<string, unknown>; teams?: Record<string, unknown> }> {
  const results: { slack?: Record<string, unknown>; teams?: Record<string, unknown> } = {};
  if (!SLACK_ALERT_TYPES.has(params.alertType)) return results;
  const prefix = PREFIX[params.alertType] ?? ':bell:';
  let body = `${prefix} *[SEO/AEO]* ${params.message}`;
  if (params.link) body += `\n<${params.link}|Mở console>`;
  if (slackWebhook()) {
    results.slack = await postJson(slackWebhook(), body);
  }
  const teamsBody = body.replace(/\*/g, '**');
  if (teamsWebhook()) {
    results.teams = await postJson(teamsWebhook(), teamsBody);
  }
  return results;
}
