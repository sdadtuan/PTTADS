'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { publicEmailConfirm } from '@/lib/api';

export default function PublicConfirmPage() {
  const params = useParams();
  const token = String(params.token ?? '');
  const [done, setDone] = useState(false);
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!token) return;
    void (async () => {
      try {
        const res = await publicEmailConfirm(token);
        if (!res.ok) {
          setError(res.error ?? 'Token không hợp lệ');
          return;
        }
        setEmail(res.email);
        setDone(true);
      } catch {
        setError('Liên kết không còn hiệu lực.');
      }
    })();
  }, [token]);

  return (
    <main style={{ maxWidth: 480, margin: '3rem auto', padding: '1.5rem', textAlign: 'center' }}>
      {error ? <p className="error">{error}</p> : null}
      {done ? (
        <>
          <h1 style={{ fontSize: '1.25rem' }}>Xác nhận đăng ký thành công.</h1>
          <p className="muted">{email}</p>
        </>
      ) : !error ? (
        <p>Đang xác nhận…</p>
      ) : null}
    </main>
  );
}
