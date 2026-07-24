import Link from 'next/link';
import type { AgencyClient } from '@/lib/api';
import { metaTrackingEnabled } from '@/lib/meta/flags';
import type { FacebookHubExportScope } from '@/lib/meta/types';

interface MetaHubFiltersProps {
  days: number;
  dateTo: string;
  dateFrom: string;
  clientId: string;
  status: string;
  q: string;
  exportScope: FacebookHubExportScope;
  clientOptions: AgencyClient[];
  loading: boolean;
  exportBusy: boolean;
  hubDateFrom?: string;
  hubDateTo?: string;
  hubWindowDays?: number;
  onDaysChange: (days: number) => void;
  onDateToChange: (value: string) => void;
  onDateFromChange: (value: string) => void;
  onClientIdChange: (value: string) => void;
  onStatusChange: (value: string) => void;
  onQueryChange: (value: string) => void;
  onExportScopeChange: (scope: FacebookHubExportScope) => void;
  onRefresh: () => void;
  onExport: () => void;
}

export function MetaHubFilters({
  days,
  dateTo,
  dateFrom,
  clientId,
  status,
  q,
  exportScope,
  clientOptions,
  loading,
  exportBusy,
  hubDateFrom,
  hubDateTo,
  hubWindowDays,
  onDaysChange,
  onDateToChange,
  onDateFromChange,
  onClientIdChange,
  onStatusChange,
  onQueryChange,
  onExportScopeChange,
  onRefresh,
  onExport,
}: MetaHubFiltersProps) {
  return (
    <div className="card" style={{ marginBottom: '1rem' }}>
      <h1 style={{ marginTop: 0, fontSize: '1.25rem' }}>Meta Ads Hub</h1>
      <p className="muted" style={{ marginTop: 0 }}>
        Closed-loop spend + CPL · kỳ {hubDateFrom ?? '—'} → {hubDateTo ?? '—'}
        {hubWindowDays ? ` (${hubWindowDays} ngày)` : ''}
      </p>
      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
        <Link href="/meta/ads-combined" className="btn btn-sm btn-secondary">
          Meta + Google
        </Link>
        <Link href="/google/google-ads" className="btn btn-sm btn-secondary">
          Google Ads hub
        </Link>
        <Link href="/crm/hub" className="btn btn-sm btn-secondary">
          Hub campaign map
        </Link>
        {metaTrackingEnabled() ? (
          <Link href="/meta/tracking" className="btn btn-sm btn-secondary">
            Meta Tracking
          </Link>
        ) : null}
        <Link href="/agency/clients" className="btn btn-sm btn-secondary">
          Agency clients
        </Link>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
          gap: '0.75rem',
          marginBottom: '1rem',
        }}
      >
        <label className="muted" style={{ display: 'grid', gap: '0.25rem' }}>
          Khoảng ngày
          <select
            value={days}
            disabled={Boolean(dateFrom)}
            onChange={(e) => onDaysChange(Number(e.target.value))}
            style={{ padding: '0.4rem' }}
          >
            <option value={7}>7 ngày</option>
            <option value={14}>14 ngày</option>
            <option value={28}>28 ngày</option>
            <option value={90}>90 ngày</option>
          </select>
        </label>
        <label className="muted" style={{ display: 'grid', gap: '0.25rem' }}>
          Đến ngày
          <input
            type="date"
            value={dateTo}
            onChange={(e) => onDateToChange(e.target.value)}
            style={{ padding: '0.4rem' }}
          />
        </label>
        <label className="muted" style={{ display: 'grid', gap: '0.25rem' }}>
          Từ ngày (tuỳ chọn)
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => onDateFromChange(e.target.value)}
            style={{ padding: '0.4rem' }}
          />
        </label>
        <label className="muted" style={{ display: 'grid', gap: '0.25rem' }}>
          Client
          <select
            value={clientId}
            onChange={(e) => onClientIdChange(e.target.value)}
            style={{ padding: '0.4rem' }}
          >
            <option value="">Tất cả</option>
            {clientOptions.map((c) => (
              <option key={c.id} value={c.id}>
                {c.code || c.name} ({c.status})
              </option>
            ))}
          </select>
        </label>
        <label className="muted" style={{ display: 'grid', gap: '0.25rem' }}>
          Status
          <select
            value={status}
            onChange={(e) => onStatusChange(e.target.value)}
            style={{ padding: '0.4rem' }}
          >
            <option value="">Tất cả</option>
            <option value="active">active</option>
            <option value="onboarding">onboarding</option>
            <option value="prospect">prospect</option>
          </select>
        </label>
        <label className="muted" style={{ display: 'grid', gap: '0.25rem' }}>
          Tìm mã/tên
          <input
            value={q}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder="TCLT…"
            style={{ padding: '0.4rem' }}
          />
        </label>
      </div>

      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
        <button type="button" className="btn btn-sm" disabled={loading} onClick={onRefresh}>
          {loading ? 'Đang tải…' : 'Áp dụng / Làm mới'}
        </button>
        <select
          value={exportScope}
          onChange={(e) => onExportScopeChange(e.target.value as FacebookHubExportScope)}
          style={{ padding: '0.35rem' }}
          aria-label="Export scope"
        >
          <option value="clients">Export CSV — theo client</option>
          <option value="campaigns">Export CSV — theo campaign</option>
        </select>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          disabled={exportBusy || loading}
          onClick={onExport}
        >
          {exportBusy ? 'Đang export…' : 'Tải CSV'}
        </button>
      </div>
    </div>
  );
}
