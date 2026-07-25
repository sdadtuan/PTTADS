'use client';

import Link from 'next/link';
import { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  captureSeoCwv,
  fetchSeoClients,
  fetchSeoCwv,
  fetchSeoTechnicalIssues,
  importSeoTechnicalCsv,
  patchSeoTechnicalIssue,
  staffMe,
  staffRefresh,
  type SeoHubClientRow,
  type SeoTechnicalIssueRow,
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
import { canViewSeoTechnical, canWriteSeoTechnical } from '@/lib/seo/caps';

const SEVERITIES = ['critical', 'high', 'medium', 'low'] as const;

function severityClass(sev: string): string {
  if (sev === 'critical') return 'error';
  if (sev === 'high') return 'badge';
  return 'muted';
}

export default function SeoTechnicalPage() {
  return (
    <Suspense
      fallback={
        <main style={{ padding: '2rem' }}>
          <p className="muted">Đang tải technical console…</p>
        </main>
      }
    >
      <SeoTechnicalContent />
    </Suspense>
  );
}

function SeoTechnicalContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [clients, setClients] = useState<SeoHubClientRow[]>([]);
  const [customerId, setCustomerId] = useState('');
  const [issues, setIssues] = useState<SeoTechnicalIssueRow[]>([]);
  const [severityMatrix, setSeverityMatrix] = useState<Record<string, number>>({});
  const [severityFilter, setSeverityFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [cwvSummary, setCwvSummary] = useState<Record<string, unknown>>({});
  const [cwvSnapshots, setCwvSnapshots] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(true);
  const [cwvBusy, setCwvBusy] = useState(false);
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');

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
      if (!canViewSeoTechnical(me)) {
        setError('Không có quyền SEO Technical');
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

  const loadData = useCallback(
    async (access: string, cid: number) => {
      setLoading(true);
      setError('');
      try {
        const [issuesOut, cwvOut] = await Promise.all([
          fetchSeoTechnicalIssues(access, cid, {
            severity: severityFilter || undefined,
            status: statusFilter || undefined,
          }),
          fetchSeoCwv(access, cid),
        ]);
        setIssues(issuesOut.issues);
        setSeverityMatrix(issuesOut.severity_matrix ?? {});
        setCwvSummary(cwvOut.summary ?? {});
        setCwvSnapshots(cwvOut.snapshots ?? []);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Không tải được technical console');
      } finally {
        setLoading(false);
      }
    },
    [severityFilter, statusFilter],
  );

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
    const cid = Number.parseInt(customerId, 10);
    if (!customerId || Number.isNaN(cid)) return;
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      await loadData(access, cid);
    })();
  }, [customerId, ensureAuth, loadData]);

  const logout = () => {
    clearSession();
    router.push('/login');
  };

  const canWrite = canWriteSeoTechnical(user);

  const matrixTotal = useMemo(
    () => SEVERITIES.reduce((sum, s) => sum + (severityMatrix[s] ?? 0), 0),
    [severityMatrix],
  );

  async function handleImportCsv() {
    if (!canWrite || !customerId) return;
    const csv = window.prompt('Dán nội dung CSV (url,issue_type,severity,description)');
    if (!csv) return;
    const access = await ensureAuth();
    if (!access) return;
    try {
      const out = await importSeoTechnicalCsv(access, Number.parseInt(customerId, 10), csv);
      setToast(`Đã import ${out.imported} issue`);
      await loadData(access, Number.parseInt(customerId, 10));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import thất bại');
    }
  }

  async function handlePatchStatus(issueId: number, status: string) {
    if (!canWrite) return;
    const access = await ensureAuth();
    if (!access || !customerId) return;
    try {
      await patchSeoTechnicalIssue(access, issueId, { status });
      await loadData(access, Number.parseInt(customerId, 10));
      setToast(`Đã cập nhật issue #${issueId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Cập nhật thất bại');
    }
  }

  async function handleCaptureCwv() {
    if (!canWrite || !customerId) return;
    const access = await ensureAuth();
    if (!access) return;
    setCwvBusy(true);
    try {
      const out = await captureSeoCwv(access, Number.parseInt(customerId, 10));
      setToast(`Đã capture ${out.captured} URL${out.errors.length ? ` · ${out.errors.length} lỗi` : ''}`);
      await loadData(access, Number.parseInt(customerId, 10));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Capture CWV thất bại');
    } finally {
      setCwvBusy(false);
    }
  }

  return (
    <div className="page">
      <OpsNav user={user} onLogout={logout} />
      <main className="main-content">
        <div className="page-header">
          <div>
            <h1>Technical Console</h1>
            <p className="muted">S-09 · Issues, severity matrix, Core Web Vitals</p>
          </div>
          <div className="page-actions">
            <Link href="/seo/hub" className="btn btn-secondary btn-sm">
              Hub
            </Link>
            <Link href="/seo/reports" className="btn btn-secondary btn-sm">
              Báo cáo
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
            <label>
              Severity
              <select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)}>
                <option value="">Tất cả</option>
                {SEVERITIES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Status
              <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                <option value="">Tất cả</option>
                <option value="open">Open</option>
                <option value="in_progress">In progress</option>
                <option value="closed">Closed</option>
                <option value="verified">Verified</option>
              </select>
            </label>
            {canWrite && (
              <button type="button" className="btn btn-sm" onClick={() => void handleImportCsv()}>
                Import CSV
              </button>
            )}
          </div>
        </div>

        {error && <p className="error">{error}</p>}
        {toast && <p className="badge">{toast}</p>}

        {!customerId ? (
          <p className="muted">Chọn client để xem technical issues.</p>
        ) : loading ? (
          <p className="muted">Đang tải…</p>
        ) : (
          <>
            <div
              className="card"
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))',
                gap: '1rem',
                marginBottom: '1rem',
              }}
            >
              {SEVERITIES.map((s) => (
                <div key={s}>
                  <p className="muted" style={{ margin: 0, textTransform: 'capitalize' }}>
                    {s}
                  </p>
                  <strong className={severityClass(s)}>{severityMatrix[s] ?? 0}</strong>
                </div>
              ))}
              <div>
                <p className="muted" style={{ margin: 0 }}>
                  Tổng
                </p>
                <strong>{matrixTotal}</strong>
              </div>
            </div>

            <div className="card" style={{ marginBottom: '1rem' }}>
              <div className="page-header" style={{ marginBottom: '0.75rem' }}>
                <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Core Web Vitals</h2>
                {canWrite && (
                  <button
                    type="button"
                    className="btn btn-sm"
                    disabled={cwvBusy}
                    onClick={() => void handleCaptureCwv()}
                  >
                    {cwvBusy ? 'Đang capture…' : 'Capture CWV'}
                  </button>
                )}
              </div>
              <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
                {Object.entries(cwvSummary).map(([key, val]) => (
                  <span key={key}>
                    <span className="muted">{key}: </span>
                    <strong>{String(val ?? '—')}</strong>
                  </span>
                ))}
                {!Object.keys(cwvSummary).length && <span className="muted">Chưa có snapshot CWV.</span>}
              </div>
              {cwvSnapshots.length > 0 && (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>URL</th>
                        <th>LCP</th>
                        <th>INP</th>
                        <th>CLS</th>
                        <th>Rating</th>
                        <th>Checked</th>
                      </tr>
                    </thead>
                    <tbody>
                      {cwvSnapshots.map((row, idx) => (
                        <tr key={String(row.id ?? idx)}>
                          <td style={{ maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {String(row.url ?? '—')}
                          </td>
                          <td>{String(row.lcp_ms ?? row.lcp ?? '—')}</td>
                          <td>{String(row.inp_ms ?? row.inp ?? '—')}</td>
                          <td>{String(row.cls ?? '—')}</td>
                          <td>{String(row.cwv_rating ?? row.rating ?? '—')}</td>
                          <td>{String(row.checked_at ?? '—')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>URL</th>
                    <th>Loại</th>
                    <th>Severity</th>
                    <th>Status</th>
                    <th>Mô tả</th>
                    <th>Phát hiện</th>
                    {canWrite && <th />}
                  </tr>
                </thead>
                <tbody>
                  {issues.map((issue) => (
                    <tr key={issue.id}>
                      <td style={{ maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {issue.url}
                      </td>
                      <td>{issue.issue_type}</td>
                      <td>
                        <span className={severityClass(issue.severity)}>{issue.severity}</span>
                      </td>
                      <td>{issue.status}</td>
                      <td>{issue.description || '—'}</td>
                      <td>{issue.discovered_at ?? '—'}</td>
                      {canWrite && (
                        <td>
                          {issue.status === 'open' && (
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              onClick={() => void handlePatchStatus(issue.id, 'in_progress')}
                            >
                              → Progress
                            </button>
                          )}
                          {issue.status === 'in_progress' && (
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              onClick={() => void handlePatchStatus(issue.id, 'closed')}
                            >
                              → Close
                            </button>
                          )}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
              {!issues.length && <p className="muted">Không có issue phù hợp bộ lọc.</p>}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
