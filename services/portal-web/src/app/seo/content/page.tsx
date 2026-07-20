'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { PortalNav } from '@/components/PortalNav';
import { portalSeoPendingContent, portalMe } from '@/lib/api';
import { clearSession, getStoredUser, getToken, type StoredUser } from '@/lib/auth';

export default function SeoContentPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredUser | null>(null);
  const [items, setItems] = useState<Array<{ id: number; title: string; content_type: string }>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async (token: string) => {
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
        return load(token);
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
      <PortalNav user={user} onLogout={logout} seoEnabled />
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
