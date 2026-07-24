import type { MetaAdsOpsPilotCheck } from './meta-ads-ops.types';

export type { MetaAdsOpsPilotCheck };

export function checkMetaAdsOpsPilot(clientId: string): MetaAdsOpsPilotCheck {
  const enabled = ['1', 'true', 'yes', 'on'].includes(
    (process.env.PTT_META_ADS_OPS_ENABLED ?? '0').trim().toLowerCase(),
  );
  if (!enabled) {
    return { allowed: false, reason: 'PTT_META_ADS_OPS_ENABLED=0' };
  }
  const raw = (process.env.PTT_META_ADS_OPS_PILOT_CLIENTS ?? '').trim();
  if (!raw) {
    return { allowed: true, pilot_mode: false };
  }
  const allow = new Set(raw.split(',').map((p) => p.trim()).filter(Boolean));
  if (!allow.has(clientId.trim())) {
    return { allowed: false, reason: 'client_not_in_pilot', pilot_mode: true };
  }
  return { allowed: true, pilot_mode: true };
}

export function metaAdsManagerDeepLink(params: {
  externalAccountId: string;
  externalCampaignId?: string;
  externalAdId?: string;
}): string {
  const account = params.externalAccountId.replace(/^act_/, '');
  const base = `https://business.facebook.com/adsmanager/manage/campaigns?act=${account}`;
  const parts = [base];
  if (params.externalCampaignId) {
    parts.push(`selected_campaign_ids=${encodeURIComponent(params.externalCampaignId)}`);
  }
  if (params.externalAdId) {
    parts.push(`selected_ad_ids=${encodeURIComponent(params.externalAdId)}`);
  }
  return parts.join('&');
}
