'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { PortalNav } from '@/components/PortalNav';
import { SeoWidgetsPanel } from '@/components/SeoWidgetsPanel';
import { portalMe, portalSeoSummary } from '@/lib/api';
import { clearSession, getStoredUser, getToken, type StoredUser } from '@/lib/auth';

export default function SeoDashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredUser | null>(null);
  const [token, setToken] = useState('');
  const [seoEnabled, setSeoEnabled] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const authToken = getToken();
    const cached = getStoredUser();
    if (!authToken) {
      router.replace('/login');
      return;
    }
    setToken(authToken);
    if (cached) {
      setUser(cached);
    }
    portalMe(authToken)
      .then((me) => setUser(me))
      .catch(() => {
        clearSession();
        router.replace('/login');
      });
    portalSeoSummary(authToken)
      .then((data) => {
        setSeoEnabled(data.seo_enabled !== false);
        if (!data.seo_enabled) {
          setError('SEO chưa được kích hoạt cho client này.');
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Lỗi tải SEO summary'));
  }, [router]);

  function logout() {
    clearSession();
    router.push('/login');
  }

  if (!token) {
    return (
      <main style={{ padding: '2rem' }}>
        <p className="muted">Đang tải…</p>
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 960, margin: '0 auto', padding: '1.5rem' }}>
      <PortalNav user={user} onLogout={logout} seoEnabled={seoEnabled} />
      {error ? <p className="error">{error}</p> : null}
      {seoEnabled ? <SeoWidgetsPanel token={token} /> : null}
    </main>
  );
}
