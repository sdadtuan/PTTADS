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

export interface CampaignWritePilotCheck {
  allowed: boolean;
  stub_mode: boolean;
  pilot_mode: boolean;
  warning?: string | null;
  reason?: string | null;
}

export function checkCampaignWritePilot(
  clientId: string,
  externalCampaignId: string,
): CampaignWritePilotCheck {
  const stubMode = truthy('PTT_META_CAMPAIGN_WRITE_STUB', '0');
  if (stubMode) {
    return {
      allowed: true,
      stub_mode: true,
      pilot_mode: false,
      warning: 'Stub mode — Meta Graph không gọi thật',
    };
  }
  const pilotMode = truthy('PTT_META_CAMPAIGN_WRITE_PILOT', '0');
  if (!pilotMode) {
    return {
      allowed: false,
      stub_mode: false,
      pilot_mode: false,
      warning: 'Pilot mode tắt — execution có thể fail trên prod',
      reason: 'pilot_mode_disabled',
    };
  }
  const clients = pilotSet('PTT_META_CAMPAIGN_WRITE_PILOT_CLIENTS');
  const campaigns = pilotSet('PTT_META_CAMPAIGN_WRITE_PILOT_CAMPAIGNS');
  const cid = clientId.trim();
  const camp = externalCampaignId.trim();
  if (clients.size && !clients.has(cid)) {
    return {
      allowed: false,
      stub_mode: false,
      pilot_mode: true,
      warning: 'Client ngoài pilot allowlist — execution có thể fail',
      reason: 'client_not_in_pilot',
    };
  }
  if (campaigns.size && !campaigns.has(camp)) {
    return {
      allowed: false,
      stub_mode: false,
      pilot_mode: true,
      warning: 'Campaign ngoài pilot allowlist — execution có thể fail',
      reason: 'campaign_not_in_pilot',
    };
  }
  return { allowed: true, stub_mode: false, pilot_mode: true, warning: null };
}
