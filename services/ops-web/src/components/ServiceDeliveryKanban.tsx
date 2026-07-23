'use client';

import Link from 'next/link';
import type { ServiceLifecycleRow } from '@/lib/api';

const STAGES = ['lead', 'consult', 'proposal', 'onboard', 'deliver', 'handover', 'retain'] as const;
const STAGE_LABELS: Record<string, string> = {
  lead: 'Lead',
  consult: 'Tư vấn',
  proposal: 'Báo giá',
  onboard: 'Onboard',
  deliver: 'Triển khai',
  handover: 'Bàn giao',
  retain: 'Giữ chân',
};

type Props = {
  rows: ServiceLifecycleRow[];
  funnelStats?: Record<string, number>;
};

export function ServiceDeliveryKanban({ rows, funnelStats }: Props) {
  const byStage: Record<string, ServiceLifecycleRow[]> = {};
  for (const s of STAGES) byStage[s] = [];
  for (const row of rows) {
    const st = String(row.stage ?? 'lead');
    if (!byStage[st]) byStage[st] = [];
    byStage[st].push(row);
  }

  return (
    <div style={{ display: 'grid', gap: '1rem' }}>
      {funnelStats && Object.keys(funnelStats).length > 0 ? (
        <div className="card" style={{ padding: '0.75rem 1rem' }}>
          <strong>Funnel active</strong>
          <span className="muted" style={{ marginLeft: '0.5rem' }}>
            {STAGES.map((s) => `${STAGE_LABELS[s] ?? s}: ${funnelStats[s] ?? 0}`).join(' · ')}
          </span>
        </div>
      ) : null}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
          gap: '0.65rem',
          alignItems: 'start',
        }}
      >
        {STAGES.map((stage) => (
          <div
            key={stage}
            style={{
              background: 'var(--bg)',
              border: '1px solid var(--border)',
              borderRadius: 10,
              minHeight: 120,
              padding: '0.5rem',
            }}
          >
            <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.4rem' }}>
              {STAGE_LABELS[stage] ?? stage}
              <span className="muted" style={{ marginLeft: 4 }}>
                ({byStage[stage]?.length ?? 0})
              </span>
            </div>
            <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'grid', gap: '0.35rem' }}>
              {(byStage[stage] ?? []).map((lc) => (
                <li key={lc.id}>
                  <Link
                    href={`/crm/service-delivery/${lc.id}`}
                    className="nav-link"
                    style={{
                      display: 'block',
                      padding: '0.35rem 0.45rem',
                      borderRadius: 6,
                      border: '1px solid var(--border)',
                      fontSize: '0.82rem',
                    }}
                  >
                    #{lc.id} · {lc.service_slug}
                    {lc.customer_id ? ` · KH #${lc.customer_id}` : ''}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
