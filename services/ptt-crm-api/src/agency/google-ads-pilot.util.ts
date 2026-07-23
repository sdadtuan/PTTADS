function truthy(name: string, defaultVal = '0'): boolean {
  return ['1', 'true', 'yes', 'on'].includes(
    String(process.env[name] ?? defaultVal)
      .trim()
      .toLowerCase(),
  );
}

function pilotSet(name: string): Set<string> {
  const raw = String(process.env[name] ?? '').trim();
  if (!raw) return new Set();
  return new Set(raw.split(',').map((p) => p.trim()).filter(Boolean));
}

export interface GoogleAdsPilotStatus {
  stub_mode: boolean;
  pilot_mode: boolean;
  insights_sync_enabled: boolean;
  oauth_configured: boolean;
  pilot_clients: string[];
  warning?: string | null;
}

export function checkGoogleAdsPilot(clientId?: string): {
  allowed: boolean;
  stub_mode: boolean;
  pilot_mode: boolean;
  warning?: string | null;
} {
  const stubMode = truthy('PTT_GOOGLE_ADS_STUB', '0');
  if (stubMode) {
    return {
      allowed: true,
      stub_mode: true,
      pilot_mode: false,
      warning: 'Stub mode — Google Ads API không gọi thật',
    };
  }
  const pilotMode = truthy('PTT_GOOGLE_ADS_PILOT', '0');
  if (!pilotMode) {
    return {
      allowed: false,
      stub_mode: false,
      pilot_mode: false,
      warning: 'Pilot mode tắt — sync Google có thể fail trên prod',
    };
  }
  const clients = pilotSet('PTT_GOOGLE_ADS_PILOT_CLIENTS');
  const cid = String(clientId ?? '').trim();
  if (clients.size && cid && !clients.has(cid)) {
    return {
      allowed: false,
      stub_mode: false,
      pilot_mode: true,
      warning: 'Client ngoài pilot allowlist — sync Google có thể fail',
    };
  }
  return { allowed: true, stub_mode: false, pilot_mode: true, warning: null };
}

export function googleAdsPilotStatus(clientId?: string): GoogleAdsPilotStatus {
  const check = checkGoogleAdsPilot(clientId);
  const oauthConfigured = Boolean(
    process.env.PTT_GOOGLE_ADS_CLIENT_ID?.trim() &&
      process.env.PTT_GOOGLE_ADS_CLIENT_SECRET?.trim() &&
      process.env.PTT_GOOGLE_OAUTH_REDIRECT_URI?.trim(),
  );
  return {
    stub_mode: check.stub_mode,
    pilot_mode: check.pilot_mode,
    insights_sync_enabled: truthy('PTT_GOOGLE_INSIGHTS_SYNC', '0'),
    oauth_configured: oauthConfigured,
    pilot_clients: [...pilotSet('PTT_GOOGLE_ADS_PILOT_CLIENTS')],
    warning: check.warning ?? null,
  };
}
