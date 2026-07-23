'use client';

import { useEffect, useState } from 'react';
import { CreativeHistoryList } from '@/components/CreativeHistoryList';
import { CreativeInbox } from '@/components/CreativeInbox';
import { PortalPageShell } from '@/components/PortalPageShell';
import {
  approveCreative,
  fetchCreativeHistory,
  fetchPendingCreatives,
  rejectCreative,
  type CreativeRow,
} from '@/lib/api';

type Tab = 'pending' | 'history';

export default function CreativesPage() {
  const [tab, setTab] = useState<Tab>('pending');
  const [pendingRows, setPendingRows] = useState<CreativeRow[]>([]);
  const [historyRows, setHistoryRows] = useState<CreativeRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  return (
    <PortalPageShell>
      {({ token, user }) => (
        <CreativesContent
          token={token}
          canApprove={user.role === 'approver'}
          tab={tab}
          setTab={setTab}
          pendingRows={pendingRows}
          setPendingRows={setPendingRows}
          historyRows={historyRows}
          setHistoryRows={setHistoryRows}
          loading={loading}
          setLoading={setLoading}
          error={error}
          setError={setError}
        />
      )}
    </PortalPageShell>
  );
}

function CreativesContent(props: {
  token: string;
  canApprove: boolean;
  tab: Tab;
  setTab: (tab: Tab) => void;
  pendingRows: CreativeRow[];
  setPendingRows: (rows: CreativeRow[]) => void;
  historyRows: CreativeRow[];
  setHistoryRows: (rows: CreativeRow[]) => void;
  loading: boolean;
  setLoading: (v: boolean) => void;
  error: string;
  setError: (v: string) => void;
}) {
  const {
    token,
    canApprove,
    tab,
    setTab,
    pendingRows,
    setPendingRows,
    historyRows,
    setHistoryRows,
    loading,
    setLoading,
    error,
    setError,
  } = props;

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError('');
      try {
        if (tab === 'pending') {
          const data = await fetchPendingCreatives(token);
          if (!cancelled) setPendingRows(data.rows);
        } else {
          const data = await fetchCreativeHistory(token, 30);
          if (!cancelled) setHistoryRows(data.rows);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Không tải được danh sách creative');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [token, tab, setPendingRows, setHistoryRows, setLoading, setError]);

  return (
    <>
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
        <button
          type="button"
          className={`btn${tab === 'pending' ? '' : ' btn-secondary'}`}
          onClick={() => setTab('pending')}
        >
          Chờ duyệt
        </button>
        <button
          type="button"
          className={`btn${tab === 'history' ? '' : ' btn-secondary'}`}
          onClick={() => setTab('history')}
        >
          Lịch sử 30 ngày
        </button>
      </div>
      {!canApprove && tab === 'pending' ? (
        <p className="muted" style={{ marginBottom: '1rem' }}>
          Tài khoản viewer — chỉ xem danh sách; cần role approver để duyệt/từ chối.
        </p>
      ) : null}
      {error ? <p className="error">{error}</p> : null}
      {loading ? (
        <p className="muted">Đang tải…</p>
      ) : tab === 'pending' ? (
        <CreativeInbox
          rows={pendingRows}
          canApprove={canApprove}
          onApprove={async (id) => {
            await approveCreative(token, id);
            const data = await fetchPendingCreatives(token);
            setPendingRows(data.rows);
          }}
          onReject={async (id, note) => {
            await rejectCreative(token, id, note);
            const data = await fetchPendingCreatives(token);
            setPendingRows(data.rows);
          }}
        />
      ) : (
        <CreativeHistoryList rows={historyRows} />
      )}
    </>
  );
}
