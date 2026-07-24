import Link from 'next/link';
import { MetaBadge } from '@/components/meta/MetaBadge';
import type { PreflightItem } from '@/lib/meta/types';

interface Props {
  items: PreflightItem[];
  clientId?: string;
  onRefresh?: () => void;
  refreshing?: boolean;
}

export function MetaPreflightChecklist({ items, clientId, onRefresh, refreshing }: Props) {
  const passed = items.filter((i) => i.passed).length;

  return (
    <div className="card meta-tracking-section meta-preflight">
      <div className="meta-preflight-header">
        <div>
          <h2 className="meta-tracking-section-title">Launch preflight (Meta)</h2>
          <p className="muted meta-preflight-subtitle">
            {passed}/{items.length} mục pass · auto-sync với Launch QA
          </p>
        </div>
        <div className="meta-preflight-actions">
          {onRefresh ? (
            <button
              type="button"
              className="btn btn-sm btn-secondary"
              disabled={refreshing}
              onClick={onRefresh}
            >
              {refreshing ? 'Đang refresh…' : 'Refresh'}
            </button>
          ) : null}
          <Link
            href={clientId ? `/crm/launch-qa?client_id=${encodeURIComponent(clientId)}` : '/crm/launch-qa'}
            className="btn btn-sm btn-secondary"
          >
            Launch QA board
          </Link>
        </div>
      </div>
      <ul className="meta-preflight-list">
        {items.map((item) => (
          <li key={item.key} className="meta-preflight-item">
            <MetaBadge variant={item.passed ? 'ok' : 'error'}>{item.passed ? 'Pass' : 'Fail'}</MetaBadge>
            <div>
              <strong>{item.label}</strong>
              {item.note ? <p className="muted meta-preflight-note">{item.note}</p> : null}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function buildPreflightItems(
  accounts: Array<{ pixel_id: string | null; capi_enabled: boolean; last_sent_at: string | null }>,
): PreflightItem[] {
  const account = accounts[0];
  const pixelOk = Boolean(account?.pixel_id);
  return [
    {
      key: 'meta_pixel_configured',
      label: 'Pixel ID đã cấu hình',
      passed: pixelOk,
      note: pixelOk ? `Pixel ${account?.pixel_id}` : 'Cấu hình pixel trên agency client',
    },
    {
      key: 'meta_capi_test_ok',
      label: 'CAPI test event OK',
      passed: false,
      note: 'Chạy Test pixel trên bảng accounts',
    },
    {
      key: 'meta_hub_map_coverage',
      label: 'Hub map ≥80% spend',
      passed: false,
      note: 'Xem Meta Ads hub · map campaign',
    },
    {
      key: 'meta_capi_recent_sent',
      label: 'CAPI sent trong 48h',
      passed: Boolean(account?.last_sent_at),
      note: account?.last_sent_at ? 'Đã có CAPI sent' : 'Chờ webhook / conversion sync',
    },
  ];
}

export function preflightFromHealthAccounts(
  accounts: Array<{ pixel_id: string | null; capi_enabled: boolean; last_sent_at: string | null }>,
): PreflightItem[] {
  return buildPreflightItems(accounts);
}
