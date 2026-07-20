'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import {
  fetchPublicEmailPreferences,
  publicEmailConfirm,
  publicEmailUnsubscribe,
  updatePublicEmailPreferences,
} from '@/lib/api';

export default function PublicEmailPreferencesPage() {
  const params = useParams();
  const token = String(params.token ?? '');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const [view, setView] = useState<{
    client_name: string;
    email: string;
    topics: Array<{ topic: string; status: string }>;
    token_purpose: string;
  } | null>(null);
  const [marketing, setMarketing] = useState(true);

  useEffect(() => {
    if (!token) return;
    void (async () => {
      setLoading(true);
      try {
        const res = await fetchPublicEmailPreferences(token);
        if (!res.ok && (res as { error?: string }).error) {
          setError((res as { error?: string }).error ?? 'Token không hợp lệ');
          return;
        }
        setView(res);
        const m = res.topics.find((t) => t.topic === 'marketing');
        setMarketing(m?.status === 'opted_in');
      } catch {
        setError('Liên kết không còn hiệu lực.');
      } finally {
        setLoading(false);
      }
    })();
  }, [token]);

  async function save() {
    setError('');
    const res = await updatePublicEmailPreferences(token, { marketing });
    if (!res.ok) {
      setError(res.error ?? 'Lưu thất bại');
      return;
    }
    setSaved(true);
  }

  if (loading) {
    return (
      <main style={{ maxWidth: 480, margin: '3rem auto', padding: '1rem' }}>
        <p>Đang tải…</p>
      </main>
    );
  }

  if (error && !view) {
    return (
      <main style={{ maxWidth: 480, margin: '3rem auto', padding: '1rem' }}>
        <p className="error">{error}</p>
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 480, margin: '3rem auto', padding: '1.5rem' }}>
      <h1 style={{ fontSize: '1.25rem' }}>{view?.client_name ?? 'Email preferences'}</h1>
      <p className="muted">{view?.email}</p>
      {saved ? <p className="badge">Đã cập nhật tùy chọn.</p> : null}
      {error ? <p className="error">{error}</p> : null}
      <label style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', margin: '1rem 0' }}>
        <input type="checkbox" checked={marketing} onChange={(e) => setMarketing(e.target.checked)} />
        Nhận email marketing
      </label>
      <button type="button" className="btn" onClick={() => void save()}>
        Lưu tùy chọn
      </button>
      <p style={{ marginTop: '1.5rem' }}>
        <a href={`/email/public/unsubscribe/${encodeURIComponent(token)}`}>Hủy đăng ký tất cả</a>
      </p>
    </main>
  );
}
