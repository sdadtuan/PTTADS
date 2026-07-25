'use client';

import Link from 'next/link';
import type { SeoClientTab } from '@/lib/seo/types';

const INTERNAL_TABS: Array<{ key: SeoClientTab; label: string }> = [
  { key: 'overview', label: 'Tổng quan' },
  { key: 'tasks', label: 'Tasks' },
  { key: 'settings', label: 'Settings' },
];

const MODULE_LINKS = [
  { href: '/seo/strategy', label: 'Strategy' },
  { href: '/seo/research', label: 'Research' },
  { href: '/seo/content', label: 'Content' },
  { href: '/seo/technical', label: 'Technical' },
  { href: '/seo/aeo', label: 'AEO' },
  { href: '/seo/authority', label: 'Authority' },
  { href: '/seo/reports', label: 'Reports' },
] as const;

export function SeoClientWorkspaceNav({
  customerId,
  activeTab,
  onTabChange,
  domains,
  markets,
}: {
  customerId: number;
  activeTab: SeoClientTab;
  onTabChange: (tab: SeoClientTab) => void;
  domains?: string[];
  markets?: string[];
}) {
  const domainLine = domains?.filter(Boolean).join(', ') || '—';
  const marketLine = markets?.filter(Boolean).join(', ');

  return (
    <>
      <p className="muted" style={{ margin: '0.5rem 0 0', fontSize: '0.9rem' }}>
        {domainLine}
        {marketLine ? ` · ${marketLine}` : ''}
      </p>

      <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', flexWrap: 'wrap' }}>
        {INTERNAL_TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            className={activeTab === t.key ? 'btn btn-sm' : 'btn btn-secondary btn-sm'}
            onClick={() => onTabChange(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem', flexWrap: 'wrap' }}>
        {MODULE_LINKS.map((m) => (
          <Link
            key={m.href}
            href={`${m.href}?customer_id=${customerId}`}
            className="btn btn-secondary btn-sm"
          >
            {m.label}
          </Link>
        ))}
      </div>
    </>
  );
}
