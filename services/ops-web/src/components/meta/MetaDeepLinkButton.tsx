'use client';

import { useEffect, useState } from 'react';
import { fetchMetaAdsOpsDeepLink } from '@/lib/meta/api';
import { getAccessToken } from '@/lib/auth';

interface MetaDeepLinkButtonProps {
  clientId: string;
  externalCampaignId?: string;
  externalAdId?: string;
}

export function MetaDeepLinkButton({ clientId, externalCampaignId, externalAdId }: MetaDeepLinkButtonProps) {
  const [url, setUrl] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    const token = getAccessToken();
    if (!token || !clientId) return;
    void fetchMetaAdsOpsDeepLink(token, {
      client_id: clientId,
      external_campaign_id: externalCampaignId,
      external_ad_id: externalAdId,
    })
      .then((out) => setUrl(out.url))
      .catch((err) => setError(err instanceof Error ? err.message : 'Deep link failed'));
  }, [clientId, externalCampaignId, externalAdId]);

  if (error) return <span className="muted">{error}</span>;
  if (!url) return <span className="muted">Đang tạo deep link…</span>;

  return (
    <a href={url} target="_blank" rel="noreferrer" className="btn btn-secondary">
      Mở Ads Manager ↗
    </a>
  );
}
