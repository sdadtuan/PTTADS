'use client';

import Link from 'next/link';
import { Suspense, useCallback, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  fetchSeoClients,
  fetchSeoGovernanceCompliance,
  fetchSeoGovernancePolicies,
  fetchSeoGovernanceStatus,
  staffMe,
  staffRefresh,
  type SeoHubClientRow,
} from '@/lib/api';
import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  getStoredUser,
  updateAccessToken,
  updateStoredUser,
  type StoredStaffUser,
} from '@/lib/auth';
import { canViewSeoGovernance } from '@/lib/seo/caps';

export default function SeoGovernancePage() {
  return (
    <Suspense
      fallback={
        <main style={{ padding: '2rem' }}>
          <p className="muted">Đang tải governance hub…</p>
        </main>
      }
    >
      <SeoGovernanceContent />
    </Suspense>
  );
}

function SeoGovernanceContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [clients, setClients] = useState<SeoHubClientRow[]>([]);
  const [customerId, setCustomerId] = useState('');
  const [governanceEnabled, setGovernanceEnabled] = useState<boolean | null>(null);
  const [policies, setPolicies] = useState<Array<Record<string, unknown>>>([]);
  const [compliance, setCompliance] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const ensureAuth = useCallback(async (): Promise<string | null> => {
    let access = getAccessToken();
    if (!access) {
      router.replace('/login');
      return null;
    }
    const cached = getStoredUser();
    if (cached) setUser(cached);
    try {
      const me = await staffMe(access);
      setUser(me);
      updateStoredUser(me);
      if (!canViewSeoGovernance(me)) {
        setError('Không có quyền SEO Governance');
        return null;
      }
      return access;
    } catch {
      const refresh = getRefreshToken();
      if (!refresh) {
        clearSession();
        router.replace('/login');
        return null;
      }
      const out = await staffRefresh(refresh);
      updateAccessToken(out.access_token);
      access = out.access_token;
      const me = await staffMe(access);
      setUser(me);
      updateStoredUser(me);
      return access;
    }
  }, [router]);

  const loadGovernance = useCallback(async (access: string, cid?: number) => {
    setLoading(true);
    setError('');
    try {
      const [statusOut, policiesOut, complianceOut] = await Promise.all([
        fetchSeoGovernanceStatus(access),
        cid != null ? fetchSeoGovernancePolicies(access, cid) : Promise.resolve({ ok: true, policies: [] }),
        fetchSeoGovernanceCompliance(access, cid, 7),
      ]);
      setGovernanceEnabled(statusOut.enabled);
      setPolicies(policiesOut.policies);
      setCompliance(complianceOut.summary);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không tải được governance');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const cid = searchParams.get('customer_id');
    if (cid) setCustomerId(cid);
  }, [searchParams]);

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      const out = await fetchSeoClients(access);
      setClients(out.clients);
      if (!customerId && out.clients[0]) {
        setCustomerId(String(out.clients[0].customer_id));
      }
    })();
  }, [ensureAuth, customerId]);

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      const cid = customerId ? Number.parseInt(customerId, 10) : undefined;
      await loadGovernance(access, Number.isNaN(cid!) ? undefined : cid);
    })();
  }, [customerId, ensureAuth, loadGovernance]);

  const logout = () => {
    clearSession();
    router.push('/login');
  };

  return (
    <div className="page">
      <OpsNav user={user} onLogout={logout} />
      <main className="main-content">
        <div className="page-header">
          <div>
            <h1>Governance Hub</h1>
            <p className="muted">S-14 · Policies, compliance, content pipeline</p>
          </div>
          <div className="page-actions">
            <Link href="/seo/hub" className="btn btn-secondary btn-sm">
              Hub
            </Link>
            <Link href="/seo/content" className="btn btn-secondary btn-sm">
              Content Pipeline
            </Link>
          </div>
        </div>

        <div className="card" style={{ marginBottom: '1rem' }}>
          <div className="form-row" style={{ alignItems: 'end', gap: '1rem', flexWrap: 'wrap' }}>
            <label>
              Client
              <select value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
                <option value="">— Chọn client —</option>
                {clients.map((c) => (
                  <option key={c.customer_id} value={c.customer_id}>
                    {c.customer_name} (#{c.customer_id})
                  </option>
                ))}
              </select>
            </label>
            <div>
              <span className="muted">Governance: </span>
              {governanceEnabled == null ? (
                <span>—</span>
              ) : governanceEnabled ? (
                <span className="badge">Đang bật</span>
              ) : (
                <span className="error">Tắt</span>
              )}
            </div>
          </div>
        </div>

        {error && <p className="error">{error}</p>}

        {!customerId ? (
          <p className="muted">Chọn client để xem governance policies.</p>
        ) : loading ? (
          <p className="muted">Đang tải…</p>
        ) : (
          <>
            <div
              className="card"
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
                gap: '1rem',
                marginBottom: '1rem',
              }}
            >
              <div>
                <p className="muted" style={{ margin: 0 }}>
                  Evaluations (7d)
                </p>
                <strong>{String(compliance.evaluations ?? '—')}</strong>
              </div>
              <div>
                <p className="muted" style={{ margin: 0 }}>
                  Passed
                </p>
                <strong>{String(compliance.passed ?? '—')}</strong>
              </div>
              <div>
                <p className="muted" style={{ margin: 0 }}>
                  Failed
                </p>
                <strong className="error">{String(compliance.failed ?? '—')}</strong>
              </div>
              <div>
                <p className="muted" style={{ margin: 0 }}>
                  Pass rate
                </p>
                <strong>{compliance.pass_rate_pct != null ? `${compliance.pass_rate_pct}%` : '—'}</strong>
              </div>
            </div>

            <div className="card" style={{ marginBottom: '1rem' }}>
              <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Policies</h2>
              {policies.length > 0 ? (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Key</th>
                        <th>Tên</th>
                        <th>Rule type</th>
                        <th>Severity</th>
                        <th>Active</th>
                      </tr>
                    </thead>
                    <tbody>
                      {policies.map((p) => (
                        <tr key={String(p.id ?? p.policy_key)}>
                          <td>{String(p.policy_key ?? '—')}</td>
                          <td>{String(p.name ?? '—')}</td>
                          <td>{String(p.rule_type ?? '—')}</td>
                          <td>{String(p.severity ?? '—')}</td>
                          <td>{p.active ? '✓' : '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="muted">Chưa có policy — seed mặc định qua API.</p>
              )}
            </div>

            <div className="card">
              <p style={{ margin: 0 }}>
                Governance được đánh giá khi content chuyển trạng thái trong{' '}
                <Link href="/seo/content" className="nav-link">
                  Content Pipeline
                </Link>
                . Violations sẽ chặn approve cho đến khi override.
              </p>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
