'use client';

import Link from 'next/link';
import { useState } from 'react';
import { MetaBadge } from '@/components/meta/MetaBadge';
import { postMetaTestPixel } from '@/lib/meta/api';
import { capiBadgeFromAccount, fmtRelativeTime } from '@/lib/meta/format';
import type { TrackingHealthAccountRow } from '@/lib/meta/types';

interface Props {
  token: string;
  accounts: TrackingHealthAccountRow[];
  canConfigure: boolean;
  onTestComplete?: () => void;
}

export function MetaTrackingAccountTable({
  token,
  accounts,
  canConfigure,
  onTestComplete,
}: Props) {
  const [testingKey, setTestingKey] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, { ok: boolean; message: string }>>(
    {},
  );

  async function runTest(account: TrackingHealthAccountRow) {
    const key = `${account.client_id}:${account.channel_account_id}`;
    setTestingKey(key);
    try {
      const out = await postMetaTestPixel(token, account.client_id, account.channel_account_id);
      setTestResults((prev) => ({
        ...prev,
        [key]: {
          ok: out.ok,
          message: out.ok
            ? out.stub
              ? 'Stub OK'
              : `OK · events ${out.events_received ?? 1}`
            : out.error ?? 'Test failed',
        },
      }));
      onTestComplete?.();
    } catch (err) {
      setTestResults((prev) => ({
        ...prev,
        [key]: { ok: false, message: err instanceof Error ? err.message : 'Test failed' },
      }));
    } finally {
      setTestingKey(null);
    }
  }

  return (
    <div className="card meta-tracking-section">
      <h2 className="meta-tracking-section-title">Channel accounts</h2>
      <div style={{ overflowX: 'auto' }}>
        <table className="perf-table meta-tracking-table">
          <thead>
            <tr>
              <th>Client</th>
              <th>Pixel</th>
              <th>Page</th>
              <th>CAPI</th>
              <th>Last sent</th>
              <th>Test pixel</th>
            </tr>
          </thead>
          <tbody>
            {accounts.map((account) => {
              const key = `${account.client_id}:${account.channel_account_id}`;
              const badge = capiBadgeFromAccount(account);
              const test = testResults[key];
              return (
                <tr key={key}>
                  <td>
                    <Link href={`/agency/clients/${account.client_id}`} className="nav-link">
                      {account.client_code || account.client_name || account.client_id.slice(0, 8)}
                    </Link>
                  </td>
                  <td>{account.pixel_id ?? '—'}</td>
                  <td>{account.page_id ?? '—'}</td>
                  <td>
                    <MetaBadge variant={badge.variant}>{badge.label}</MetaBadge>
                  </td>
                  <td>{fmtRelativeTime(account.last_sent_at)}</td>
                  <td>
                    {canConfigure && account.pixel_id ? (
                      <div className="meta-tracking-test-cell">
                        <button
                          type="button"
                          className="btn btn-sm btn-secondary"
                          disabled={testingKey === key}
                          onClick={() => void runTest(account)}
                        >
                          {testingKey === key ? 'Đang test…' : 'Test pixel'}
                        </button>
                        {test ? (
                          <span
                            className={
                              test.ok ? 'meta-tracking-test-ok' : 'meta-tracking-test-fail'
                            }
                          >
                            {test.message}
                          </span>
                        ) : null}
                      </div>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
            {!accounts.length ? (
              <tr>
                <td colSpan={6} className="muted">
                  Không có channel account Meta active
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
