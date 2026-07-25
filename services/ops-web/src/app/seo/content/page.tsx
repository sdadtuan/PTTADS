'use client';

import Link from 'next/link';
import { Suspense, useCallback, useEffect, useState } from 'react';
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

function SeoContentPipelineContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [clients, setClients] = useState<SeoHubClientRow[]>([]);
  const [customerId, setCustomerId] = useState('');
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
  }, [searchParams]);

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
          <label>
            Client filter
            <select value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
              <option value="">Tất cả clients</option>
              {clients.map((c) => (
                <option key={c.customer_id} value={c.customer_id}>
                  {c.customer_name} (#{c.customer_id})
                </option>
              ))}
            </select>
          </label>
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
            {(board?.columns ?? []).map((col) => (
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
