'use client';

import Link from 'next/link';
import { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  fetchSeoClients,
  fetchSeoContentPipeline,
  staffMe,
  staffRefresh,
  type SeoContentRow,
  type SeoHubClientRow,
  type SeoPipelineBoard,
} from '@/lib/api';
import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  getStoredUser,
  updateAccessToken,
  updateStoredUser,
  type StoredStaffUser,
} from '@/lib/auth';
import { canViewSeoContent } from '@/lib/seo/caps';

export default function SeoContentPipelinePage() {
  return (
    <Suspense
      fallback={
        <main style={{ padding: '2rem' }}>
          <p className="muted">Đang tải pipeline…</p>
        </main>
      }
    >
      <SeoContentPipelineContent />
    </Suspense>
  );
}

const REVIEW_STATUSES = new Set([
  'seo_review',
  'aeo_review',
  'technical_review',
  'client_review',
]);

type PipelineView = 'all' | 'review' | 'refresh';

function SeoContentPipelineContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [clients, setClients] = useState<SeoHubClientRow[]>([]);
  const [customerId, setCustomerId] = useState('');
  const [view, setView] = useState<PipelineView>('all');
  const [board, setBoard] = useState<SeoPipelineBoard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const ensureAuth = useCallback(async (): Promise<string | null> => {
    let access = getAccessToken();
    if (!access) {
      router.replace('/login');
      return null;
    }
    const cached = getStoredUser();
    if (cached) setUser(cached);
    try {
      const me = await staffMe(access);
      setUser(me);
      updateStoredUser(me);
      if (!canViewSeoContent(me)) {
        setError('Không có quyền SEO Content');
        return null;
      }
      return access;
    } catch {
      const refresh = getRefreshToken();
      if (!refresh) {
        clearSession();
        router.replace('/login');
        return null;
      }
      const out = await staffRefresh(refresh);
      updateAccessToken(out.access_token);
      access = out.access_token;
      const me = await staffMe(access);
      setUser(me);
      updateStoredUser(me);
      return access;
    }
  }, [router]);

  const loadBoard = useCallback(
    async (access: string, cid?: number) => {
      setLoading(true);
      setError('');
      try {
        const out = await fetchSeoContentPipeline(access, {
          customer_id: cid,
        });
        setBoard(out.board);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Không tải được pipeline');
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    const cid = searchParams.get('customer_id');
    if (cid) setCustomerId(cid);
    const rawView = searchParams.get('view');
    if (rawView === 'review' || rawView === 'refresh') setView(rawView);
  }, [searchParams]);

  const filteredBoard = useMemo(() => {
    if (!board || view === 'all') return board;
    const reviewKeys = new Set(['seo_review', 'aeo_review', 'technical_review', 'client_review']);
    const columns = board.columns
      .map((col) => {
        const items =
          view === 'refresh'
            ? col.items.filter((item) => item.workflow_status === 'refresh_required')
            : col.items.filter((item) => REVIEW_STATUSES.has(item.workflow_status));
        return { ...col, items };
      })
      .filter((col) => (view === 'refresh' ? col.key === 'refresh' : reviewKeys.has(col.key)));
    return { ...board, columns };
  }, [board, view]);

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      const out = await fetchSeoClients(access);
      setClients(out.clients);
    })();
  }, [ensureAuth]);

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      const cid = customerId ? Number.parseInt(customerId, 10) : undefined;
      await loadBoard(access, Number.isNaN(cid!) ? undefined : cid);
    })();
  }, [customerId, ensureAuth, loadBoard]);

  const logout = () => {
    clearSession();
    router.push('/login');
  };

  function Card({ item }: { item: SeoContentRow }) {
    const overdue = item.due_date && new Date(item.due_date) < new Date();
    return (
      <Link href={`/seo/content/${item.id}`} className="card" style={{ display: 'block', marginBottom: '0.5rem' }}>
        <strong>{item.title}</strong>
        <div className="muted" style={{ fontSize: '0.85rem' }}>
          #{item.id} · {item.workflow_status}
          {item.due_date ? ` · due ${item.due_date}` : ''}
        </div>
        {overdue && <span className="error" style={{ fontSize: '0.75rem' }}>Quá hạn</span>}
      </Link>
    );
  }

  return (
    <div className="page">
      <OpsNav user={user} onLogout={logout} />
      <main className="main-content">
        <div className="page-header">
          <div>
            <h1>Nội dung — Pipeline</h1>
            <p className="muted">Kanban 10 cột — research → brief → review → publish</p>
          </div>
          <div className="page-actions">
            <Link href="/seo/research" className="btn btn-secondary btn-sm">
              Research
            </Link>
            <Link href="/seo/hub" className="btn btn-secondary btn-sm">
              Hub
            </Link>
          </div>
        </div>

        <div className="card" style={{ marginBottom: '1rem' }}>
          <div className="form-row" style={{ alignItems: 'end', gap: '1rem', flexWrap: 'wrap' }}>
            <label>
              Client filter
              <select
                value={customerId}
                onChange={(e) => {
                  const next = e.target.value;
                  setCustomerId(next);
                  const qs = new URLSearchParams();
                  if (next) qs.set('customer_id', next);
                  if (view !== 'all') qs.set('view', view);
                  router.replace(`/seo/content${qs.toString() ? `?${qs.toString()}` : ''}`);
                }}
              >
                <option value="">Tất cả clients</option>
                {clients.map((c) => (
                  <option key={c.customer_id} value={c.customer_id}>
                    {c.customer_name} (#{c.customer_id})
                  </option>
                ))}
              </select>
            </label>
            <label>
              View
              <select
                value={view}
                onChange={(e) => {
                  const next = e.target.value as PipelineView;
                  setView(next);
                  const qs = new URLSearchParams();
                  if (customerId) qs.set('customer_id', customerId);
                  if (next !== 'all') qs.set('view', next);
                  router.replace(`/seo/content${qs.toString() ? `?${qs.toString()}` : ''}`);
                }}
              >
                <option value="all">Full pipeline</option>
                <option value="review">Review only</option>
                <option value="refresh">Cần refresh</option>
              </select>
            </label>
          </div>
        </div>

        {error && <p className="error">{error}</p>}
        {loading ? (
          <p className="muted">Đang tải pipeline…</p>
        ) : (
          <div
            style={{
              display: 'grid',
              gridAutoFlow: 'column',
              gridAutoColumns: 'minmax(220px, 1fr)',
              gap: '0.75rem',
              overflowX: 'auto',
              paddingBottom: '1rem',
            }}
          >
            {(filteredBoard?.columns ?? []).map((col) => (
              <div key={col.key} className="card" style={{ minHeight: 320 }}>
                <h3 style={{ fontSize: '0.95rem', marginBottom: '0.5rem' }}>
                  {col.label} ({col.items.length})
                </h3>
                {col.items.length === 0 ? (
                  <p className="muted" style={{ fontSize: '0.85rem' }}>
                    Trống
                  </p>
                ) : (
                  col.items.map((item) => <Card key={item.id} item={item} />)
                )}
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
