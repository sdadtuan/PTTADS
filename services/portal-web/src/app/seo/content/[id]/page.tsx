'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { PortalNav } from '@/components/PortalNav';
import { portalSeoContentDetail, portalSeoReviewContent, portalMe } from '@/lib/api';
import { clearSession, getStoredUser, getToken, type StoredUser } from '@/lib/auth';
import { usePortalSeoNav } from '@/hooks/usePortalSeoNav';

function ApprovalTimeline({ approvals }: { approvals: Array<Record<string, unknown>> }) {
  if (!approvals.length) return null;
  return (
    <section style={{ marginTop: '1.25rem' }}>
      <h3 style={{ margin: '0 0 0.5rem', fontSize: '1rem' }}>Approval timeline</h3>
      <ul style={{ margin: 0, paddingLeft: '1.2rem' }}>
        {approvals.map((row) => (
          <li key={String(row.stage)} style={{ marginBottom: '0.35rem' }}>
            <strong>{String(row.stage)}</strong>: {String(row.status ?? 'pending')}
            {row.actor_id ? <span className="muted"> — {String(row.actor_id)}</span> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function SeoContentDetailPage() {
  const router = useRouter();
  const params = useParams();
  const contentId = String(params.id || '');
  const [user, setUser] = useState<StoredUser | null>(null);
  const [token, setToken] = useState('');
  const [content, setContent] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState('');
  const seoEnabled = usePortalSeoNav(token || null);

  useEffect(() => {
    const authToken = getToken();
    if (!authToken) {
      router.replace('/login');
      return;
    }
    setToken(authToken);
    const cached = getStoredUser();
    if (cached) setUser(cached);
    portalMe(authToken)
      .then((me) => {
        setUser(me);
        return portalSeoContentDetail(authToken, contentId);
      })
      .then(setContent)
      .catch((err) => setError(err instanceof Error ? err.message : 'Lỗi tải content'))
      .catch(() => {
        clearSession();
        router.replace('/login');
      });
  }, [router, contentId]);

  function logout() {
    clearSession();
    router.push('/login');
  }

  async function review(approved: boolean) {
    const authToken = getToken();
    if (!authToken || !user) return;
    const notes = window.prompt('Ghi chú (optional):') || '';
    try {
      await portalSeoReviewContent(authToken, contentId, { approved, notes });
      router.push('/seo/content');
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Duyệt thất bại');
    }
  }

  const brief = (content?.brief as Record<string, unknown>) ?? {};
  const approvals = (content?.approvals as Array<Record<string, unknown>>) ?? [];

  return (
    <main style={{ maxWidth: 900, margin: '0 auto', padding: '1.5rem' }}>
      <PortalNav user={user} onLogout={logout} seoEnabled={seoEnabled} />
      {error && <p className="error">{error}</p>}
      {content && (
        <section className="card">
          <h1 style={{ marginTop: 0, fontSize: '1.25rem' }}>{String(content.title)}</h1>
          <p className="muted">
            Status: {String(content.workflow_status)} · Type: {String(content.content_type)}
          </p>
          {(Boolean(brief.meta_title) || Boolean(brief.meta_description)) && (
            <div style={{ marginTop: '0.75rem', fontSize: '0.9rem' }}>
              {brief.meta_title ? (
                <p style={{ margin: '0.25rem 0' }}>
                  <strong>Meta title:</strong> {String(brief.meta_title)}
                </p>
              ) : null}
              {brief.meta_description ? (
                <p style={{ margin: '0.25rem 0' }}>
                  <strong>Meta description:</strong> {String(brief.meta_description)}
                </p>
              ) : null}
            </div>
          )}
          <div
            style={{ marginTop: '1rem', padding: '1rem', background: '#f9fafb', borderRadius: 8 }}
            dangerouslySetInnerHTML={{ __html: String(content.body_html || '') }}
          />
          <ApprovalTimeline approvals={approvals} />
          {user?.role === 'approver' && content.workflow_status === 'client_review' ? (
            <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem' }}>
              <button type="button" className="btn" data-testid="seo-approve-btn" onClick={() => review(true)}>
                ✓ Approve
              </button>
              <button type="button" className="btn btn-secondary" data-testid="seo-reject-btn" onClick={() => review(false)}>
                ✗ Reject
              </button>
            </div>
          ) : null}
        </section>
      )}
    </main>
  );
}
