import type { MetaAlertRow } from '@/lib/meta/types';

export function buildMetaAdsOpsEditUrl(params: {
  clientId: string;
  externalAdId: string;
  disapproved?: boolean;
}): string {
  const qs = new URLSearchParams({
    mode: 'edit',
    client_id: params.clientId,
    ad_id: params.externalAdId,
  });
  if (params.disapproved) qs.set('ack', '1');
  return `/meta/ads-ops?${qs.toString()}`;
}

export function parseDisapprovedAdId(alert: MetaAlertRow): string | null {
  if (alert.alert_type !== 'ad_disapproved') return null;
  const match = alert.message.match(/Meta ad (\S+) disapproved/);
  if (match?.[1]) return match[1];
  return alert.external_campaign_id;
}
