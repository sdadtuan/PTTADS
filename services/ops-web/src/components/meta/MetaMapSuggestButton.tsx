'use client';

import { useState } from 'react';
import Link from 'next/link';
import { postMetaHubMapSuggest } from '@/lib/meta/api';
import { getAccessToken } from '@/lib/auth';

interface MetaMapSuggestButtonProps {
  clientId: string;
  dateFrom?: string;
  dateTo?: string;
  disabled?: boolean;
  onDone?: (insertedCount: number) => void;
}

export function MetaMapSuggestButton({
  clientId,
  dateFrom,
  dateTo,
  disabled,
  onDone,
}: MetaMapSuggestButtonProps) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [linkHub, setLinkHub] = useState(false);

  const handleClick = async () => {
    const access = getAccessToken();
    if (!access || busy) return;
    setBusy(true);
    setMessage('');
    setLinkHub(false);
    try {
      const out = await postMetaHubMapSuggest(access, {
        client_id: clientId,
        date_from: dateFrom,
        date_to: dateTo,
        dry_run: false,
      });
      const count = out.inserted_count ?? out.inserted?.length ?? 0;
      if (count > 0) {
        setMessage(`Đã gợi ý map ${count} campaign.`);
        setLinkHub(true);
        onDone?.(count);
      } else {
        setMessage('Không tìm thấy map phù hợp (score ≥ 60).');
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Gợi ý map thất bại');
    } finally {
      setBusy(false);
    }
  };

  return (
    <span style={{ display: 'inline-flex', flexDirection: 'column', gap: '0.25rem' }}>
      <button
        type="button"
        className="btn btn-sm btn-secondary"
        disabled={disabled || busy}
        onClick={() => void handleClick()}
      >
        {busy ? 'Đang gợi ý…' : 'Gợi ý map'}
      </button>
      {message ? (
        <span className="muted" style={{ fontSize: '0.75rem', maxWidth: '12rem' }}>
          {message}{' '}
          {linkHub ? (
            <Link href="/crm/hub" className="nav-link">
              Mở Hub
            </Link>
          ) : null}
        </span>
      ) : null}
    </span>
  );
}
