'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import type { StoredUser } from '@/lib/auth';

interface PortalNavProps {
  user: StoredUser | null;
  onLogout: () => void;
}

const PAGE_TITLES: Record<string, string> = {
  '/dashboard': 'Performance',
  '/meta': 'Meta Performance',
  '/creatives': 'Creative inbox',
};

export function PortalNav({ user, onLogout }: PortalNavProps) {
  const pathname = usePathname();
  const links = [
    { href: '/dashboard', label: 'Performance' },
    { href: '/meta', label: 'Meta (Facebook)' },
    { href: '/creatives', label: 'Creative inbox' },
  ];

  const pageTitle = PAGE_TITLES[pathname] ?? 'Dashboard';

  return (
    <header
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '1.5rem',
        gap: '1rem',
        flexWrap: 'wrap',
      }}
    >
      <div>
        <p className="badge">Client portal</p>
        <h1 style={{ margin: '0.35rem 0 0', fontSize: '1.35rem' }}>{pageTitle}</h1>
        <p className="muted" style={{ margin: '0.25rem 0 0' }}>
          {user?.email} · {user?.role}
        </p>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
        <nav style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={`nav-link${pathname === link.href ? ' active' : ''}`}
            >
              {link.label}
            </Link>
          ))}
        </nav>
        <button type="button" className="btn btn-secondary" onClick={onLogout}>
          Đăng xuất
        </button>
      </div>
    </header>
  );
}
