'use client';

import { MetaBadge } from '@/components/meta/MetaBadge';
import { fmtDateTime } from '@/lib/meta/format';
import { useMetaSyncStatus } from '@/hooks/meta/useMetaSyncStatus';
import type { MetaBadgeVariant } from '@/lib/meta/types';

interface MetaSyncStatusChipProps {
  clientId?: string;
}

function statusVariant(status: 'ok' | 'warn' | 'error' | undefined): MetaBadgeVariant {
  if (status === 'error') return 'error';
  if (status === 'warn') return 'warn';
  return 'ok';
}

function statusLabel(status: 'ok' | 'warn' | 'error' | undefined, loading: boolean): string {
  if (loading) return 'Sync…';
  if (status === 'error') return 'Sync lỗi';
  if (status === 'warn') return 'Sync cảnh báo';
  return 'Sync OK';
}

export function MetaSyncStatusChip({ clientId }: MetaSyncStatusChipProps) {
  const { data, loading, error } = useMetaSyncStatus(clientId);
  const global = data?.global;
  const variant = error ? 'error' : statusVariant(global?.status);
  const label = error ? 'Sync ?' : statusLabel(global?.status, loading);

  const title = [
    global?.last_success_at ? `OK: ${fmtDateTime(global.last_success_at)}` : null,
    global?.last_sync_at ? `Last: ${fmtDateTime(global.last_sync_at)}` : null,
    global?.last_error ? `Error: ${global.last_error}` : null,
    global?.accounts_failed ? `Failed accounts: ${global.accounts_failed}` : null,
    error,
  ]
    .filter(Boolean)
    .join(' · ');

  return (
    <MetaBadge variant={variant} title={title || undefined}>
      {label}
    </MetaBadge>
  );
}
