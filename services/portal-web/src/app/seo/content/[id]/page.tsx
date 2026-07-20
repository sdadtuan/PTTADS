'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { PortalNav } from '@/components/PortalNav';
import { portalSeoContentDetail, portalSeoReviewContent, portalMe } from '@/lib/api';
import { clearSession, getStoredUser, getToken, type StoredUser } from '@/lib/auth';

export default function SeoContentDetailPage() {
  const router = useRouter();
  const params = useParams();
  const contentId = String(params.id || '');
  const [user, setUser] = useState<StoredUser | null>(null);
  const [content, setContent] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace('/login');
      return;
    }
    const cached = getStoredUser();
    if (cached) setUser(cached);
    portalMe(token)
      .then((me) => {
        setUser(me);
        return portalSeoContentDetail(token, contentId);
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
    const token = getToken();
    if (!token || !user) return;
    const notes = window.prompt('Ghi chú (optional):') || '';
    try {
      await portalSeoReviewContent(token, contentId, { approved, notes });
      router.push('/seo/content');
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Duyệt thất bại');
    }
  }

  return (
    <main style={{ maxWidth: 900, margin: '0 auto', padding: '1.5rem' }}>
      <PortalNav user={user} onLogout={logout} seoEnabled />
      {error && <p className="error">{error}</p>}
      {content && (
        <section className="card">
          <h1 style={{ marginTop: 0, fontSize: '1.25rem' }}>{String(content.title)}</h1>
          <p className="muted">Status: {String(content.workflow_status)}</p>
          <div
            style={{ marginTop: '1rem', padding: '1rem', background: '#f9fafb', borderRadius: 8 }}
            dangerouslySetInnerHTML={{ __html: String(content.body_html || '') }}
          />
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
