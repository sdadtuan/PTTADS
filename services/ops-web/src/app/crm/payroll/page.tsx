'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  computePayroll,
  exportPayrollJson,
  fetchPayrollAttendance,
  fetchPayrollDashboard,
  fetchPayrollPeriod,
  fetchPayrollPolicy,
  staffMe,
  staffRefresh,
} from '@/lib/api';
import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  getStoredUser,
  hasCap,
  updateAccessToken,
  updateStoredUser,
  type StoredStaffUser,
} from '@/lib/auth';

export default function CrmPayrollPage() {
  const router = useRouter();
  const now = new Date();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [tab, setTab] = useState<'dashboard' | 'payroll' | 'attendance' | 'policy'>('dashboard');
  const [dashboard, setDashboard] = useState<Record<string, unknown> | null>(null);
  const [payroll, setPayroll] = useState<Record<string, unknown> | null>(null);
  const [lines, setLines] = useState<Array<Record<string, unknown>>>([]);
  const [attendance, setAttendance] = useState<Array<Record<string, unknown>>>([]);
  const [policy, setPolicy] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [computing, setComputing] = useState(false);

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
      const canView =
        hasCap(me, 'crm_payroll_salary', 'view') ||
        hasCap(me, 'crm_payroll_attendance', 'view') ||
        hasCap(me, 'crm_staff_roster', 'view');
      if (!canView) {
        setError('Không có quyền payroll');
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

  const loadTab = useCallback(
    async (access: string) => {
      setLoading(true);
      setError('');
      try {
        if (tab === 'dashboard') {
          setDashboard(await fetchPayrollDashboard(access, { year, month }));
        } else if (tab === 'payroll') {
          const out = await fetchPayrollPeriod(access, year, month);
          setPayroll(out.payroll);
          setLines(out.lines ?? []);
        } else if (tab === 'attendance') {
          setAttendance(await fetchPayrollAttendance(access));
        } else if (tab === 'policy') {
          setPolicy(await fetchPayrollPolicy(access));
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải payroll thất bại');
      } finally {
        setLoading(false);
      }
    },
    [tab, year, month],
  );

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      await loadTab(access);
    })();
  }, [ensureAuth, loadTab]);

  async function onCompute() {
    const access = getAccessToken();
    if (!access) return;
    setComputing(true);
    setError('');
    try {
      const out = await computePayroll(access, { year, month });
      setPayroll(out.payroll);
      setLines(out.lines ?? []);
      setTab('payroll');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tính lương thất bại');
    } finally {
      setComputing(false);
    }
  }

  async function onExport() {
    const access = getAccessToken();
    if (!access) return;
    setError('');
    try {
      const bundle = await exportPayrollJson(access, { year, month });
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `payroll-${year}-${month}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export thất bại');
    }
  }

  function logout() {
    clearSession();
    router.push('/login');
  }

  if (!user) {
    return (
      <main style={{ padding: '2rem' }}>
        <p className="muted">Đang tải…</p>
      </main>
    );
  }

  const canEdit = hasCap(user, 'crm_payroll_salary', 'edit');
  const canExport =
    hasCap(user, 'crm_payroll_salary', 'export') ||
    hasCap(user, 'crm_payroll_salary', 'view') ||
    hasCap(user, 'crm_payroll_salary', 'edit');

  return (
    <main style={{ maxWidth: 960, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: '1.15rem' }}>Payroll & chấm công</h2>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
          <input
            type="number"
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            style={{
              width: 90,
              background: 'var(--bg)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: '0.55rem 0.75rem',
              color: 'var(--text)',
            }}
          />
          <input
            type="number"
            min={1}
            max={12}
            value={month}
            onChange={(e) => setMonth(Number(e.target.value))}
            style={{
              width: 70,
              background: 'var(--bg)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: '0.55rem 0.75rem',
              color: 'var(--text)',
            }}
          />
          {canEdit ? (
            <button type="button" className="btn btn-sm" disabled={computing} onClick={() => void onCompute()}>
              Tính lương
            </button>
          ) : null}
          {canExport ? (
            <button type="button" className="btn btn-sm btn-secondary" onClick={() => void onExport()}>
              Export JSON
            </button>
          ) : null}
        </div>
        <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
          {(['dashboard', 'payroll', 'attendance', 'policy'] as const).map((t) => (
            <button
              key={t}
              type="button"
              className={`btn btn-sm${tab === t ? '' : ' btn-secondary'}`}
              onClick={() => setTab(t)}
            >
              {t === 'dashboard' ? 'Dashboard' : t === 'payroll' ? 'Bảng lương' : t === 'attendance' ? 'Chấm công' : 'Chính sách'}
            </button>
          ))}
        </div>
        {loading ? <p className="muted">Đang tải…</p> : null}
        {error ? <p className="error">{error}</p> : null}

        {tab === 'dashboard' && dashboard ? (
          <pre
            style={{
              background: 'var(--bg)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: '0.75rem',
              overflow: 'auto',
              fontSize: '0.85rem',
            }}
          >
            {JSON.stringify(dashboard, null, 2)}
          </pre>
        ) : null}

        {tab === 'payroll' ? (
          <>
            {payroll ? (
              <p className="muted">
                Kỳ {String(payroll.year)}-{String(payroll.month)} · {String(payroll.status ?? 'draft')}
              </p>
            ) : (
              <p className="muted">Chưa có bảng lương kỳ này.</p>
            )}
            <ul style={{ margin: 0, paddingLeft: '1.1rem' }}>
              {lines.map((line, i) => (
                <li key={String(line.id ?? i)}>
                  {String(line.staff_name ?? line.staff_id ?? '—')} · gross{' '}
                  {Number(line.gross_vnd ?? line.base_salary_vnd ?? 0).toLocaleString('vi-VN')} VND
                </li>
              ))}
            </ul>
          </>
        ) : null}

        {tab === 'attendance' ? (
          <ul style={{ margin: 0, paddingLeft: '1.1rem' }}>
            {attendance.slice(0, 50).map((a, i) => (
              <li key={String(a.id ?? i)}>
                {String(a.staff_name ?? a.staff_id ?? '—')} · {String(a.work_date ?? '—')} · in{' '}
                {String(a.time_in ?? '—')} out {String(a.time_out ?? '—')}
              </li>
            ))}
          </ul>
        ) : null}

        {tab === 'policy' && policy ? (
          <pre
            style={{
              background: 'var(--bg)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: '0.75rem',
              overflow: 'auto',
              fontSize: '0.85rem',
            }}
          >
            {JSON.stringify(policy, null, 2)}
          </pre>
        ) : null}
      </div>
    </main>
  );
}
