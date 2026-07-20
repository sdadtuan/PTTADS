'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { PortalNav } from '@/components/PortalNav';
import { portalMe, portalSeoExecutiveReport, type PortalSeoReportType } from '@/lib/api';
import { clearSession, getStoredUser, getToken, type StoredUser } from '@/lib/auth';

const REPORT_TABS: { id: PortalSeoReportType; label: string }[] = [
  { id: 'executive', label: 'Tổng quan' },
  { id: 'seo', label: 'SEO' },
  { id: 'aeo', label: 'AEO' },
  { id: 'technical', label: 'Kỹ thuật' },
  { id: 'content', label: 'Nội dung' },
];

const REPORT_TAB_IDS = new Set(REPORT_TABS.map((t) => t.id));

function tabFromQuery(raw: string | null): PortalSeoReportType {
  if (raw && REPORT_TAB_IDS.has(raw as PortalSeoReportType)) {
    return raw as PortalSeoReportType;
  }
  return 'executive';
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <p className="muted" style={{ margin: 0, fontSize: '0.85rem' }}>
        {label}
      </p>
      <strong style={{ fontSize: '1.15rem' }}>{value}</strong>
    </div>
  );
}

function ReportBody({ report }: { report: Record<string, unknown> }) {
  const gsc = (report.gsc as Record<string, unknown>) || {};
  const aeo = (report.aeo as Record<string, unknown>) || {};
  const authority = (report.authority as Record<string, unknown>) || {};
  const contentByStatus = (report.content_by_status as Record<string, number>) || {};
  const severity = (report.severity as Record<string, number>) || {};
  const issues = (report.issues as Array<Record<string, string>>) || [];
  const mentions = (report.mentions_recent as Array<Record<string, unknown>>) || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {(gsc.clicks != null || gsc.impressions != null) && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit,minmax(120px,1fr))',
            gap: '1rem',
          }}
        >
          {gsc.clicks != null && <Stat label="Clicks (GSC)" value={String(gsc.clicks)} />}
          {gsc.impressions != null && <Stat label="Impressions" value={String(gsc.impressions)} />}
          {gsc.avg_ctr != null && (
            <Stat label="Avg CTR" value={`${(Number(gsc.avg_ctr) * 100).toFixed(2)}%`} />
          )}
          {gsc.queries != null && <Stat label="Queries" value={String(gsc.queries)} />}
        </div>
      )}

      {report.critical_issues != null && (
        <Stat label="Critical issues (open)" value={String(report.critical_issues)} />
      )}

      {aeo.coverage_pct != null && (
        <Stat
          label="AEO coverage"
          value={`${aeo.coverage_pct}% (${aeo.visible ?? 0}/${aeo.total ?? 0} queries)`}
        />
      )}

      {authority.total_signals != null && (
        <Stat label="Authority signals" value={String(authority.total_signals)} />
      )}

      {Object.keys(contentByStatus).length > 0 && (
        <section>
          <h3 style={{ margin: '0 0 0.5rem', fontSize: '1rem' }}>Content pipeline</h3>
          <ul style={{ margin: 0, paddingLeft: '1.2rem' }}>
            {Object.entries(contentByStatus).map(([k, v]) => (
              <li key={k}>
                <strong>{k}</strong>: {v}
              </li>
            ))}
          </ul>
        </section>
      )}

      {Object.keys(severity).length > 0 && (
        <section>
          <h3 style={{ margin: '0 0 0.5rem', fontSize: '1rem' }}>Severity matrix</h3>
          <ul style={{ margin: 0, paddingLeft: '1.2rem' }}>
            {Object.entries(severity).map(([k, v]) => (
              <li key={k}>
                <strong>{k}</strong>: {v}
              </li>
            ))}
          </ul>
        </section>
      )}

      {issues.length > 0 && (
        <section>
          <h3 style={{ margin: '0 0 0.5rem', fontSize: '1rem' }}>Open technical issues</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
            <thead>
              <tr>
                <th align="left">URL</th>
                <th align="left">Type</th>
                <th align="left">Severity</th>
                <th align="left">Status</th>
              </tr>
            </thead>
            <tbody>
              {issues.map((row, i) => (
                <tr key={i}>
                  <td>{row.url}</td>
                  <td>{row.issue_type}</td>
                  <td>{row.severity}</td>
                  <td>{row.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {mentions.length > 0 && (
        <section>
          <h3 style={{ margin: '0 0 0.5rem', fontSize: '1rem' }}>AI mentions (30 ngày)</h3>
          <ul style={{ margin: 0, paddingLeft: '1.2rem' }}>
            {mentions.map((m, i) => (
              <li key={i}>
                {String(m.stat_date ?? '—')} — {String(m.mention_count ?? 0)} mentions (
                {String(m.citation_status ?? '')})
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

export default function SeoReportsPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredUser | null>(null);
  const [tab, setTab] = useState<PortalSeoReportType>('executive');
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [generatedAt, setGeneratedAt] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const params = new URLSearchParams(window.location.search);
    setTab(tabFromQuery(params.get('tab')));
  }, []);

  const loadReport = useCallback(async (token: string, type: PortalSeoReportType) => {
    setLoading(true);
    setError('');
    try {
      const data = await portalSeoExecutiveReport(token, type);
      setReport(data.report);
      setGeneratedAt(data.generated_at);
    } catch (err) {
      setReport(null);
      setError(err instanceof Error ? err.message : 'Không tải được báo cáo');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace('/login');
      return;
    }
    const cached = getStoredUser();
    if (cached) setUser(cached);
    portalMe(token)
      .then((me) => {
        setUser(me);
        return loadReport(token, tab);
      })
      .catch(() => {
        clearSession();
        router.replace('/login');
      });
  }, [router, tab, loadReport]);

  function logout() {
    clearSession();
    router.push('/login');
  }

  return (
    <main style={{ maxWidth: 960, margin: '0 auto', padding: '1.5rem' }}>
      <PortalNav user={user} onLogout={logout} seoEnabled />

      <section className="card">
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            gap: '1rem',
            flexWrap: 'wrap',
            marginBottom: '1rem',
          }}
        >
          <div>
            <h2 style={{ margin: 0 }}>Báo cáo SEO/AEO</h2>
            <p className="muted" style={{ margin: '0.35rem 0 0' }}>
              Read-only · {generatedAt ? `Cập nhật ${generatedAt}` : 'Đang tải…'}
            </p>
          </div>
          <Link href="/seo/content" className="btn btn-secondary btn-sm">
            Nội dung chờ duyệt →
          </Link>
        </div>

        <nav style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
          {REPORT_TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              className={`nav-link${tab === t.id ? ' active' : ''}`}
              onClick={() => {
                setTab(t.id);
                router.replace(`/seo/reports?tab=${t.id}`, { scroll: false });
              }}
              style={{ cursor: 'pointer', border: 'none', background: 'transparent' }}
            >
              {t.label}
            </button>
          ))}
        </nav>

        {error && <p className="error">{error}</p>}
        {loading ? (
          <p className="muted">Đang tải báo cáo…</p>
        ) : report ? (
          <ReportBody report={report} />
        ) : null}
      </section>
    </main>
  );
}
