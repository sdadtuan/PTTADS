'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { EmailWidgetsPanel } from '@/components/EmailWidgetsPanel';
import { PortalNav } from '@/components/PortalNav';
import { portalEmailDashboard, portalMe } from '@/lib/api';
import { clearSession, getStoredUser, getToken, type StoredUser } from '@/lib/auth';

export default function PortalEmailDashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredUser | null>(null);
  const [token, setToken] = useState('');
  const [emailEnabled, setEmailEnabled] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const authToken = getToken();
    const cached = getStoredUser();
    if (!authToken) {
      router.replace('/login');
      return;
    }
    setToken(authToken);
    if (cached) setUser(cached);
    portalMe(authToken)
      .then((me) => setUser(me))
      .catch(() => {
        clearSession();
        router.replace('/login');
      });
    portalEmailDashboard(authToken)
      .then((data) => {
        setEmailEnabled(data.email_enabled !== false);
        if (!data.email_enabled) {
          setError('Email chưa được kích hoạt cho client này (cần workspace).');
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Lỗi tải email'));
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
      <PortalNav user={user} onLogout={logout} emailEnabled={emailEnabled} />
      <div className="card" style={{ marginBottom: '1rem' }}>
        <p className="muted" style={{ marginTop: 0 }}>EM-4 P-EMAIL-01 — Client email dashboard</p>
        {user?.role === 'approver' ? (
          <Link href="/email/approvals" className="btn btn-sm">
            Approval inbox →
          </Link>
        ) : null}
      </div>
      {error ? <p className="error">{error}</p> : null}
      {emailEnabled ? <EmailWidgetsPanel token={token} /> : null}
    </main>
  );
}
