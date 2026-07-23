'use client';

type Props = {
  pilot?: Record<string, unknown> | null;
};

export function GooglePilotBanner({ pilot }: Props) {
  if (!pilot) return null;
  const warning = String(pilot.warning ?? '').trim();
  const stub = Boolean(pilot.stub_mode);
  const oauthOk = Boolean(pilot.oauth_configured);
  const syncEnabled = Boolean(pilot.insights_sync_enabled);
  if (!warning && oauthOk && syncEnabled && !stub) return null;
  return (
    <div
      className="card"
      style={{
        marginBottom: '1rem',
        borderColor: warning ? 'var(--accent)' : undefined,
        padding: '0.75rem 1rem',
      }}
    >
      <p style={{ margin: '0 0 0.35rem', fontWeight: 600 }}>Google Ads pilot</p>
      <p className="muted" style={{ margin: 0, fontSize: '0.9rem' }}>
        OAuth: {oauthOk ? 'configured' : 'missing env'} · Sync: {syncEnabled ? 'on' : 'off'}
        {stub ? ' · stub mode' : ''}
      </p>
      {warning ? (
        <p className="error" style={{ margin: '0.5rem 0 0', fontSize: '0.9rem' }}>
          {warning}
        </p>
      ) : null}
    </div>
  );
}
