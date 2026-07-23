'use client';

import Link from 'next/link';
import { clearSession } from '@/lib/auth';

export default function ArchivedPage() {
  return (
    <main
      style={{
        minHeight: '100vh',
        display: 'grid',
        placeItems: 'center',
        padding: '1.5rem',
      }}
    >
      <div className="card" style={{ width: '100%', maxWidth: 480 }}>
        <p className="badge" style={{ marginBottom: '0.75rem' }}>
          Client archived
        </p>
        <h1 style={{ margin: '0 0 0.35rem', fontSize: '1.5rem' }}>Portal đã đóng</h1>
        <p className="muted" style={{ marginTop: 0 }}>
          Tài khoản client này đã được offboard — không thể đăng nhập hay làm mới phiên. Liên hệ AM PTT nếu
          cần hỗ trợ.
        </p>
        <button
          type="button"
          className="btn"
          style={{ marginTop: '1rem' }}
          onClick={() => {
            clearSession();
            window.location.href = '/login';
          }}
        >
          Về trang đăng nhập
        </button>
        <p className="muted" style={{ marginTop: '1rem', marginBottom: 0 }}>
          <Link href="/login">Đăng nhập tài khoản khác</Link>
        </p>
      </div>
    </main>
  );
}
