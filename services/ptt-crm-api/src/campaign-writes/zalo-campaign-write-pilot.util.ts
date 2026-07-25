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

export interface ZaloCampaignWritePilotCheck {
  allowed: boolean;
  stub_mode: boolean;
  pilot_mode: boolean;
  warning?: string | null;
  reason?: string | null;
}

export function checkZaloCampaignWritePilot(
  clientId: string,
  externalCampaignId: string,
): ZaloCampaignWritePilotCheck {
  const stubMode = truthy('PTT_ZALO_CAMPAIGN_WRITE_STUB', '0');
  if (stubMode) {
    return {
      allowed: true,
      stub_mode: true,
      pilot_mode: false,
      warning: 'Stub mode — Zalo Business API không gọi thật',
    };
  }
  const pilotMode = truthy('PTT_ZALO_CAMPAIGN_WRITE_PILOT', '0');
  if (!pilotMode) {
    return {
      allowed: false,
      stub_mode: false,
      pilot_mode: false,
      warning: 'Pilot mode tắt — cần Zalo Business API write permission + PTT_ZALO_CAMPAIGN_WRITE_PILOT=1',
      reason: 'pilot_mode_disabled',
    };
  }
  const clients = pilotSet('PTT_ZALO_CAMPAIGN_WRITE_PILOT_CLIENTS');
  const campaigns = pilotSet('PTT_ZALO_CAMPAIGN_WRITE_PILOT_CAMPAIGNS');
  const cid = clientId.trim();
  const camp = externalCampaignId.trim();
  if (clients.size && !clients.has(cid)) {
    return {
      allowed: false,
      stub_mode: false,
      pilot_mode: true,
      warning: 'Client ngoài pilot allowlist',
      reason: 'client_not_in_pilot',
    };
  }
  if (campaigns.size && camp && !camp.startsWith('pending:') && !campaigns.has(camp)) {
    return {
      allowed: false,
      stub_mode: false,
      pilot_mode: true,
      warning: 'Campaign ngoài pilot allowlist',
      reason: 'campaign_not_in_pilot',
    };
  }
  return { allowed: true, stub_mode: false, pilot_mode: true, warning: null };
}
