import { fmtPct, fmtVnd } from '@/lib/meta/format';
import type { HubAttributionMeta } from '@/lib/meta/types';

interface MetaHubKpiGridProps {
  summary: Record<string, unknown>;
  clientCount: number;
  attribution?: HubAttributionMeta | null;
}

export function MetaHubKpiGrid({ summary, clientCount, attribution }: MetaHubKpiGridProps) {
  const unmappedSpendPct =
    attribution?.unmapped_spend_pct ?? (summary.unmapped_spend_pct as number | undefined);

  return (
    <div className="card summary-grid" style={{ marginBottom: '1rem' }}>
      <div className="summary-card">
        <p className="muted" style={{ margin: 0 }}>
          Spend
        </p>
        <strong>{fmtVnd(Number(summary.total_spend ?? 0))}</strong>
      </div>
      <div className="summary-card">
        <p className="muted" style={{ margin: 0 }}>
          Leads CRM
        </p>
        <strong>{String(summary.total_leads ?? 0)}</strong>
      </div>
      <div className="summary-card">
        <p className="muted" style={{ margin: 0 }}>
          CPL TB
        </p>
        <strong>{fmtVnd(summary.avg_cpl as number | null)}</strong>
      </div>
      <div className="summary-card">
        <p className="muted" style={{ margin: 0 }}>
          Clients
        </p>
        <strong>{String(summary.meta_clients ?? clientCount)}</strong>
      </div>
      <div className="summary-card">
        <p className="muted" style={{ margin: 0 }}>
          Chưa map (campaign)
        </p>
        <strong>{String(summary.unmapped_campaigns ?? 0)}</strong>
      </div>
      <div className="summary-card">
        <p className="muted" style={{ margin: 0 }}>
          Unmapped spend
        </p>
        <strong>{unmappedSpendPct != null ? fmtPct(unmappedSpendPct) : '—'}</strong>
      </div>
      <div className="summary-card">
        <p className="muted" style={{ margin: 0 }}>
          Vượt target
        </p>
        <strong>{String(summary.over_target_rows ?? 0)}</strong>
      </div>
      {summary.open_alerts != null ? (
        <div className="summary-card">
          <p className="muted" style={{ margin: 0 }}>
            Open alerts
          </p>
          <strong>{String(summary.open_alerts)}</strong>
        </div>
      ) : null}
    </div>
  );
}
