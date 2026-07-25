'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { PortalNav } from '@/components/PortalNav';
import { portalSeoPendingContent, portalMe } from '@/lib/api';
import { clearSession, getStoredUser, getToken, type StoredUser } from '@/lib/auth';
import { usePortalSeoNav } from '@/hooks/usePortalSeoNav';

export default function SeoContentPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredUser | null>(null);
  const [items, setItems] = useState<Array<{ id: number; title: string; content_type: string }>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [token, setToken] = useState('');
  const seoEnabled = usePortalSeoNav(token || null);

  const load = useCallback(async (authToken: string) => {
    setLoading(true);
    try {
      const data = await portalSeoPendingContent(token);
      setItems(data.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không tải được danh sách');
    } finally {
      setLoading(false);
    }
  }, []);

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
        return load(authToken);
      })
      .catch(() => {
        clearSession();
        router.replace('/login');
      });
  }, [router, load]);

  function logout() {
    clearSession();
    router.push('/login');
  }

  return (
    <main style={{ maxWidth: 900, margin: '0 auto', padding: '1.5rem' }}>
      <PortalNav user={user} onLogout={logout} seoEnabled={seoEnabled} />
      <section className="card">
        <h2 style={{ marginTop: 0 }}>Nội dung chờ duyệt (client review)</h2>
        {user && user.role !== 'approver' ? (
          <p className="muted">Viewer — chỉ xem, không duyệt.</p>
        ) : null}
        {error && <p className="error">{error}</p>}
        {loading ? (
          <p className="muted">Đang tải…</p>
        ) : items.length === 0 ? (
          <p className="muted">Không có nội dung chờ duyệt.</p>
        ) : (
          <ul>
            {items.map((item) => (
              <li key={item.id} style={{ marginBottom: '0.5rem' }}>
                <Link href={`/seo/content/${item.id}`}>{item.title}</Link>
                <span className="muted"> · {item.content_type}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
