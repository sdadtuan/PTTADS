'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { portalResetPassword, portalValidateResetToken } from '@/lib/api';

export default function ResetPasswordPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get('token') ?? '';

  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [emailMasked, setEmailMasked] = useState('');
  const [validating, setValidating] = useState(true);
  const [tokenOk, setTokenOk] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!token) {
      setValidating(false);
      setTokenOk(false);
      setError('Link không hợp lệ — thiếu token.');
      return;
    }
    void portalValidateResetToken(token)
      .then((out) => {
        if (out.ok) {
          setTokenOk(true);
          setEmailMasked(out.email_masked ?? '');
        } else {
          setError('Link hết hạn hoặc đã được sử dụng. Yêu cầu link mới.');
        }
      })
      .catch(() => setError('Không xác thực được link.'))
      .finally(() => setValidating(false));
  }, [token]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      setError('Mật khẩu xác nhận không khớp.');
      return;
    }
    if (password.length < 8) {
      setError('Mật khẩu tối thiểu 8 ký tự.');
      return;
    }
    setError('');
    setLoading(true);
    try {
      await portalResetPassword(token, password);
      router.replace('/login?reset=ok');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Đặt lại mật khẩu thất bại');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', padding: '1.5rem' }}>
      <div className="card" style={{ width: '100%', maxWidth: 420 }}>
        <h1 style={{ margin: '0 0 0.35rem', fontSize: '1.5rem' }}>Đặt mật khẩu mới</h1>
        {validating ? <p className="muted">Đang kiểm tra link…</p> : null}
        {!validating && tokenOk ? (
          <>
            {emailMasked ? (
              <p className="muted" style={{ marginTop: 0 }}>
                Tài khoản: {emailMasked}
              </p>
            ) : null}
            <form onSubmit={onSubmit}>
              <div className="field">
                <label htmlFor="password">Mật khẩu mới</label>
                <input
                  id="password"
                  type="password"
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={8}
                />
              </div>
              <div className="field">
                <label htmlFor="confirm">Xác nhận mật khẩu</label>
                <input
                  id="confirm"
                  type="password"
                  autoComplete="new-password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  required
                  minLength={8}
                />
              </div>
              {error ? <p className="error">{error}</p> : null}
              <button className="btn" type="submit" disabled={loading} style={{ width: '100%' }}>
                {loading ? 'Đang lưu…' : 'Lưu mật khẩu mới'}
              </button>
            </form>
          </>
        ) : null}
        {!validating && !tokenOk ? (
          <>
            {error ? <p className="error">{error}</p> : null}
            <p style={{ marginBottom: 0 }}>
              <Link href="/forgot-password" className="nav-link">
                Yêu cầu link mới
              </Link>
            </p>
          </>
        ) : null}
        <p style={{ marginTop: '1rem', marginBottom: 0 }}>
          <Link href="/login" className="nav-link">
            ← Đăng nhập
          </Link>
        </p>
      </div>
    </main>
  );
}
