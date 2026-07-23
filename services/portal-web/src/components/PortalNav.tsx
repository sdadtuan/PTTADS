'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import type { PortalSettingsResponse } from '@/lib/api';
import type { StoredUser } from '@/lib/auth';

interface PortalNavProps {
  user: StoredUser | null;
  onLogout: () => void;
  pendingCount?: number;
  branding?: PortalSettingsResponse | null;
  seoEnabled?: boolean;
  emailEnabled?: boolean;
}

const PAGE_TITLES: Record<string, string> = {
  '/dashboard': 'Performance',
  '/meta': 'Meta Performance',
  '/google': 'Google Performance',
  '/creatives': 'Creative inbox',
  '/settings': 'Cài đặt',
  '/seo': 'SEO/AEO',
  '/seo/reports': 'SEO Reports',
  '/seo/content': 'SEO Content review',
  '/email': 'Email dashboard',
  '/email/approvals': 'Email approvals',
};

export function PortalNav({
  user,
  onLogout,
  pendingCount = 0,
  branding,
  seoEnabled = false,
  emailEnabled = false,
}: PortalNavProps) {
  const pathname = usePathname();
  const links = [
    { href: '/dashboard', label: 'Performance' },
    { href: '/meta', label: 'Meta (Facebook)' },
    { href: '/google', label: 'Google Ads' },
    {
      href: '/creatives',
      label: pendingCount > 0 ? `Creative inbox (${pendingCount})` : 'Creative inbox',
    },
    { href: '/settings', label: 'Cài đặt' },
  ];
  if (seoEnabled) {
    links.push({ href: '/seo', label: 'SEO/AEO' });
    links.push({ href: '/seo/reports', label: 'SEO reports' });
    links.push({ href: '/seo/content', label: 'SEO review' });
  }
  if (emailEnabled) {
    links.push({ href: '/email', label: 'Email' });
    if (user?.role === 'approver') {
      links.push({ href: '/email/approvals', label: 'Email approvals' });
    }
  }

  const pageTitle =
    pathname.startsWith('/email/campaigns/') ? 'Campaign performance' : PAGE_TITLES[pathname] ?? 'Dashboard';
  const displayName = branding?.display_name ?? branding?.client_name ?? 'Client portal';

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
      <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
        {branding?.logo_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={branding.logo_url}
            alt=""
            style={{ width: 40, height: 40, objectFit: 'contain', borderRadius: 8 }}
          />
        ) : null}
        <div>
          <p className="badge" style={{ marginBottom: '0.35rem' }}>
            {displayName}
          </p>
          <h1 style={{ margin: 0, fontSize: '1.35rem' }}>{pageTitle}</h1>
          <p className="muted" style={{ margin: '0.25rem 0 0' }}>
            {user?.email} · {user?.role}
          </p>
        </div>
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
