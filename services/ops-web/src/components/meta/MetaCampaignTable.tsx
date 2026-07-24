'use client';

import { useState, Fragment } from 'react';
import Link from 'next/link';
import { MetaBreakdownPanel } from '@/components/meta/MetaBreakdownPanel';
import { MetaHubBadges } from '@/components/meta/MetaHubBadges';
import { MetaMapSuggestButton } from '@/components/meta/MetaMapSuggestButton';
import { fmtDeltaPct, fmtDeltaVnd, fmtVnd } from '@/lib/meta/format';
import { metaBreakdownEnabled } from '@/lib/meta/flags';
import type { FacebookHubCampaignRow } from '@/lib/meta/types';

interface MetaCampaignTableProps {
  rows: FacebookHubCampaignRow[];
  loading: boolean;
  token?: string | null;
  dateFrom?: string;
  dateTo?: string;
  onMapSuggestDone?: () => void;
}

export function MetaCampaignTable({
  rows,
  loading,
  token,
  dateFrom,
  dateTo,
  onMapSuggestDone,
}: MetaCampaignTableProps) {
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const breakdownOn = metaBreakdownEnabled() && Boolean(token);

  return (
    <div className="card" id="campaigns-table">
      <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Campaigns overview</h2>
      <div style={{ overflowX: 'auto' }}>
        <table className="perf-table">
          <thead>
            <tr>
              <th>Campaign</th>
              <th>Client</th>
              <th>Spend</th>
              <th>Leads</th>
              <th>CPL</th>
              <th>Target</th>
              <th>CPL Δ</th>
              <th>Badges</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const key = `${row.client_id}:${row.external_campaign_id ?? 'none'}`;
              const label = row.external_campaign_name || row.external_campaign_id || '—';
              const expanded = expandedKey === key;
              return (
                <Fragment key={key}>
                  <tr>
                    <td title={row.external_campaign_id ?? undefined}>{label}</td>
                    <td>
                      <Link href={`/agency/clients/${row.client_id}`} className="nav-link">
                        {row.client_code || row.client_name || row.client_id.slice(0, 8)}
                      </Link>
                    </td>
                    <td>{fmtVnd(row.spend)}</td>
                    <td>{row.leads_crm}</td>
                    <td>{fmtVnd(row.cpl)}</td>
                    <td>{fmtVnd(row.target_cpl_vnd)}</td>
                    <td>
                      {row.cpl_delta_vnd != null ? (
                        <span className={row.over_target ? 'error' : undefined}>
                          {fmtDeltaVnd(row.cpl_delta_vnd)} ({fmtDeltaPct(row.cpl_delta_pct)})
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td>
                      <MetaHubBadges hubMapped={row.hub_mapped} overTarget={row.over_target} />
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                        {breakdownOn && row.external_campaign_id ? (
                          <button
                            type="button"
                            className="btn-secondary btn-small"
                            onClick={() => setExpandedKey(expanded ? null : key)}
                          >
                            {expanded ? 'Ẩn breakdown' : 'Breakdown'}
                          </button>
                        ) : null}
                        {!row.hub_mapped ? (
                          <MetaMapSuggestButton
                            clientId={row.client_id}
                            dateFrom={dateFrom}
                            dateTo={dateTo}
                            onDone={() => onMapSuggestDone?.()}
                          />
                        ) : (
                          !breakdownOn ? <span className="muted">—</span> : null
                        )}
                      </div>
                    </td>
                  </tr>
                  {expanded && token && row.external_campaign_id ? (
                    <tr key={`${key}:breakdown`}>
                      <td colSpan={9}>
                        <MetaBreakdownPanel
                          token={token}
                          clientId={row.client_id}
                          campaignId={row.external_campaign_id}
                          dateFrom={dateFrom}
                          dateTo={dateTo}
                        />
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              );
            })}
            {!loading && rows.length === 0 ? (
              <tr>
                <td colSpan={9} className="muted">
                  Không có campaign Meta cho bộ lọc đã chọn
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
