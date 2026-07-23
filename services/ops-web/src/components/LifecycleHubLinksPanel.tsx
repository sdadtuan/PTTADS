'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { fetchServiceLifecycleContext } from '@/lib/api';

type Props = {
  token: string;
  lifecycleId: number;
};

export function LifecycleHubLinksPanel({ token, lifecycleId }: Props) {
  const [ctx, setCtx] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const data = await fetchServiceLifecycleContext(token, lifecycleId);
        setCtx(data);
      } catch {
        setCtx(null);
      }
    })();
  }, [token, lifecycleId]);

  if (!ctx) return null;

  const contract = ctx.contract as Record<string, unknown> | undefined;
  const campaign = ctx.campaign as Record<string, unknown> | undefined;
  const links = ctx.links as Record<string, string | null> | undefined;
  const lead = ctx.lead as Record<string, unknown> | undefined;

  return (
    <div className="card" style={{ padding: '1rem', marginBottom: '1rem' }}>
      <h3 style={{ margin: '0 0 0.5rem', fontSize: '1rem' }}>Liên kết Hub & Agency</h3>
      <ul style={{ margin: 0, paddingLeft: '1.1rem', fontSize: '0.9rem' }}>
        {links?.lead ? (
          <li>
            Lead:{' '}
            <Link href={links.lead} className="nav-link">
              #{String(lead?.id ?? '')} {String(lead?.full_name ?? '')}
            </Link>
          </li>
        ) : null}
        {contract?.id ? (
          <li>
            Hợp đồng #{String(contract.id)} · {Number(contract.amount_vnd ?? 0).toLocaleString('vi-VN')} ₫
            {contract.title ? ` — ${String(contract.title)}` : ''}
          </li>
        ) : null}
        {links?.agency_client ? (
          <li>
            Agency client:{' '}
            <Link href={links.agency_client} className="nav-link">
              {String(contract?.agency_client_id ?? 'Client')}
            </Link>
          </li>
        ) : null}
        {links?.hub ? (
          <li>
            Hub MKT:{' '}
            <Link href={links.hub} className="nav-link">
              {campaign?.name ? String(campaign.name) : 'Mở Hub'}
            </Link>
            {campaign?.code ? ` (${String(campaign.code)})` : ''}
          </li>
        ) : null}
      </ul>
    </div>
  );
}
