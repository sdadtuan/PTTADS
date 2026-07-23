'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { PerformancePanel } from '@/components/PerformancePanel';
import { PortalNav } from '@/components/PortalNav';
import { portalMe } from '@/lib/api';
import { clearSession, getStoredUser, getToken, type StoredUser } from '@/lib/auth';

export default function GooglePerformancePage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredUser | null>(null);
  const [token, setToken] = useState('');

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
  }, [router]);

  function logout() {
    clearSession();
    router.push('/login');
  }

  if (!user || !token) {
    return (
      <main style={{ padding: '2rem' }}>
        <p className="muted">Đang tải…</p>
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 1100, margin: '0 auto', padding: '1.5rem' }}>
      <PortalNav user={user} onLogout={logout} />
      <PerformancePanel
        token={token}
        channel="google"
        title="Google Performance (Google Ads)"
        subtitle="Chỉ kênh Google"
        hideChannelColumn
      />
      <p className="muted" style={{ fontSize: '0.82rem', marginTop: '0.5rem' }}>
        Báo cáo read-only từ Google Ads Insights (T-1). Liên hệ AM nếu cần điều chỉnh chiến dịch.
      </p>
    </main>
  );
}
