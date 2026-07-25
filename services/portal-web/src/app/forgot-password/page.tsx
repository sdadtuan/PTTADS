'use client';

import Link from 'next/link';
import { FormEvent, useState } from 'react';
import { portalForgotPassword } from '@/lib/api';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [devResetUrl, setDevResetUrl] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setMessage('');
    setDevResetUrl('');
    setLoading(true);
    try {
      const out = await portalForgotPassword(email.trim());
      setMessage(out.message);
      if (out.reset_url) {
        try {
          const u = new URL(out.reset_url);
          setDevResetUrl(`${u.pathname}${u.search}`);
        } catch {
          setDevResetUrl(out.reset_url);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Gửi yêu cầu thất bại');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', padding: '1.5rem' }}>
      <div className="card" style={{ width: '100%', maxWidth: 420 }}>
        <h1 style={{ margin: '0 0 0.35rem', fontSize: '1.5rem' }}>Quên mật khẩu</h1>
        <p className="muted" style={{ marginTop: 0, marginBottom: '1.25rem' }}>
          Nhập email portal — nếu tài khoản tồn tại, bạn sẽ nhận link đặt lại mật khẩu.
        </p>
        <form onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          {error ? <p className="error">{error}</p> : null}
          {message ? <p className="muted">{message}</p> : null}
          {devResetUrl ? (
            <p className="muted" style={{ fontSize: '0.85rem' }}>
              Dev/staging link:{' '}
              <Link href={devResetUrl} className="nav-link">
                Mở trang đặt lại mật khẩu
              </Link>
            </p>
          ) : null}
          <button className="btn" type="submit" disabled={loading} style={{ width: '100%' }}>
            {loading ? 'Đang gửi…' : 'Gửi link đặt lại'}
          </button>
        </form>
        <p style={{ marginTop: '1rem', marginBottom: 0 }}>
          <Link href="/login" className="nav-link">
            ← Quay lại đăng nhập
          </Link>
        </p>
      </div>
    </main>
  );
}
