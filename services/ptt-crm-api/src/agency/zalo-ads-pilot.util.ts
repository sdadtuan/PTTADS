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

export interface ZaloAdsPilotStatus {
  stub_mode: boolean;
  pilot_mode: boolean;
  insights_sync_enabled: boolean;
  oauth_configured: boolean;
  pilot_clients: string[];
  warning?: string | null;
}

export function checkZaloAdsPilot(clientId?: string): {
  allowed: boolean;
  stub_mode: boolean;
  pilot_mode: boolean;
  warning?: string | null;
} {
  const stubMode = truthy('PTT_ZALO_ADS_STUB', '0');
  if (stubMode) {
    return {
      allowed: true,
      stub_mode: true,
      pilot_mode: false,
      warning: 'Stub mode — Zalo Ads API không gọi thật',
    };
  }
  const pilotMode = truthy('PTT_ZALO_ADS_PILOT', '0');
  if (!pilotMode) {
    return {
      allowed: false,
      stub_mode: false,
      pilot_mode: false,
      warning: 'Pilot mode tắt — sync Zalo có thể fail trên prod',
    };
  }
  const clients = pilotSet('PTT_ZALO_ADS_PILOT_CLIENTS');
  const cid = String(clientId ?? '').trim();
  if (clients.size && cid && !clients.has(cid)) {
    return {
      allowed: false,
      stub_mode: false,
      pilot_mode: true,
      warning: 'Client ngoài pilot allowlist — sync Zalo có thể fail',
    };
  }
  return { allowed: true, stub_mode: false, pilot_mode: true, warning: null };
}

export function zaloAdsPilotStatus(clientId?: string): ZaloAdsPilotStatus {
  const check = checkZaloAdsPilot(clientId);
  const oauthConfigured = Boolean(
    process.env.PTT_ZALO_APP_ID?.trim() &&
      process.env.PTT_ZALO_APP_SECRET?.trim() &&
      process.env.PTT_ZALO_OAUTH_REDIRECT_URI?.trim(),
  );
  return {
    stub_mode: check.stub_mode,
    pilot_mode: check.pilot_mode,
    insights_sync_enabled: truthy('PTT_ZALO_INSIGHTS_SYNC', '0'),
    oauth_configured: oauthConfigured,
    pilot_clients: [...pilotSet('PTT_ZALO_ADS_PILOT_CLIENTS')],
    warning: check.warning ?? null,
  };
}
