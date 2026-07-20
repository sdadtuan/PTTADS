'use client';

import { FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';
import { staffLogin } from '@/lib/api';
import { saveSession } from '@/lib/auth';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const out = await staffLogin(email.trim(), password);
      saveSession(out.access_token, out.refresh_token, out.user);
      router.push('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Đăng nhập thất bại');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main
      style={{
        minHeight: '100vh',
        display: 'grid',
        placeItems: 'center',
        padding: '1.5rem',
      }}
    >
      <div className="card" style={{ width: '100%', maxWidth: 420 }}>
        <p className="badge" style={{ marginBottom: '0.75rem' }}>
          Internal Ops
        </p>
        <h1 style={{ margin: '0 0 0.35rem', fontSize: '1.5rem' }}>PTT Ops</h1>
        <p className="muted" style={{ marginTop: 0, marginBottom: '1.25rem' }}>
          Đăng nhập nhân viên — thay Flask admin dần theo migration plan
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
          <div className="field">
            <label htmlFor="password">Mật khẩu</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {error ? <p className="error">{error}</p> : null}
          <button className="btn" type="submit" disabled={loading} style={{ width: '100%' }}>
            {loading ? 'Đang đăng nhập…' : 'Đăng nhập'}
          </button>
        </form>
        <p className="muted" style={{ marginTop: '1rem', marginBottom: 0 }}>
          Dev: <code>staff@demo.local</code> / <code>demo123</code> ·{' '}
          <code>./scripts/local_ops_up.sh</code>
        </p>
      </div>
    </main>
  );
}
