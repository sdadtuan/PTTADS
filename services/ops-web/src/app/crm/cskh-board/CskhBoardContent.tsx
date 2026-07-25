'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  bulkAssignCskhLeads,
  bulkRescheduleCskhLeads,
  cskhBoardExportUrl,
  fetchCskhBoard,
  fetchCrmStaffList,
  staffMe,
  staffRefresh,
  type CskhBoardRow,
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

const PAGE_SIZE = 50;

function slaBadge(state: CskhBoardRow['sla_state']): { label: string; className: string } {
  if (state === 'breach') return { label: 'SLA breach', className: 'badge badge-danger' };
  if (state === 'warning') return { label: 'Sắp breach', className: 'badge badge-warn' };
  if (state === 'ok') return { label: 'OK', className: 'badge badge-ok' };
  return { label: '—', className: 'muted' };
}

export function CskhBoardContent() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [token, setToken] = useState('');
  const [rows, setRows] = useState<CskhBoardRow[]>([]);
  const [summary, setSummary] = useState({ total: 0, breach: 0, warning: 0, ok: 0 });
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [slaFilter, setSlaFilter] = useState<'all' | 'breach' | 'warning' | 'open'>('breach');
  const [ownerId, setOwnerId] = useState('');
  const [q, setQ] = useState('');
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [staffOptions, setStaffOptions] = useState<Array<{ id: number; name: string }>>([]);
  const [assignTo, setAssignTo] = useState('');
  const [assignReason, setAssignReason] = useState('');
  const [followUpAt, setFollowUpAt] = useState('');
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);

  const canAssign = hasCap(user, 'crm_leads', 'assign');

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
      if (!hasCap(me, 'crm_leads', 'view')) {
        setError('Không có quyền xem bảng CSKH');
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

  const loadBoard = useCallback(
    async (accessToken: string, nextOffset: number) => {
      setLoading(true);
      setError('');
      try {
        const data = await fetchCskhBoard(accessToken, {
          q: query || undefined,
          owner_id: ownerId ? Number(ownerId) : undefined,
          sla_filter: slaFilter,
          limit: PAGE_SIZE,
          offset: nextOffset,
        });
        setRows(data.items);
        setSummary(data.summary);
        setTotal(data.total);
        setOffset(data.offset);
        setSelected(new Set());
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải bảng CSKH thất bại');
      } finally {
        setLoading(false);
      }
    },
    [ownerId, query, slaFilter],
  );

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      setToken(access);
      const me = getStoredUser();
      if (me && hasCap(me, 'crm_leads', 'assign')) {
        try {
          const staff = await fetchCrmStaffList(access);
          setStaffOptions(
            staff.staff.map((s) => ({ id: Number(s.id), name: String(s.name ?? s.id) })),
          );
        } catch {
          /* optional */
        }
      }
      await loadBoard(access, 0);
    })();
  }, [ensureAuth, loadBoard]);

  const allSelected = useMemo(
    () => rows.length > 0 && rows.every((r) => selected.has(r.id)),
    [rows, selected],
  );

  function toggleAll() {
    if (allSelected) {
      setSelected(new Set());
      return;
    }
    setSelected(new Set(rows.map((r) => r.id)));
  }

  function toggleOne(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function runBulkAssign() {
    if (!token || !canAssign) return;
    const ids = [...selected];
    if (!ids.length) {
      setError('Chọn ít nhất một lead');
      return;
    }
    setBusy(true);
    setMsg('');
    setError('');
    try {
      const out = await bulkAssignCskhLeads(token, {
        lead_ids: ids,
        to_user_id: Number(assignTo),
        reason: assignReason.trim(),
      });
      setMsg(`Đã phân lại ${out.assigned}/${out.total} lead`);
      await loadBoard(token, offset);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Bulk assign thất bại');
    } finally {
      setBusy(false);
    }
  }

  async function runBulkReschedule() {
    if (!token || !canAssign) return;
    const ids = [...selected];
    if (!ids.length || !followUpAt) {
      setError('Chọn lead và thời gian follow-up');
      return;
    }
    setBusy(true);
    setMsg('');
    setError('');
    try {
      const out = await bulkRescheduleCskhLeads(token, {
        lead_ids: ids,
        follow_up_at: new Date(followUpAt).toISOString(),
      });
      setMsg(`Đã lên lịch follow-up cho ${out.rescheduled} lead`);
      await loadBoard(token, offset);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Bulk reschedule thất bại');
    } finally {
      setBusy(false);
    }
  }

  async function exportCsv() {
    if (!token) return;
    const url = cskhBoardExportUrl({
      owner_id: ownerId ? Number(ownerId) : undefined,
      sla_filter: slaFilter,
      q: query || undefined,
    });
    try {
      const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) throw new Error('Export failed');
      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = objectUrl;
      a.download = `cskh-board-${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(objectUrl);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export CSV thất bại');
    }
  }

  return (
    <main className="page-shell">
      <OpsNav user={user} onLogout={() => { clearSession(); router.replace('/login'); }} />
      <div className="page-content">
        <header className="page-header">
          <div>
            <h1>Bảng CSKH — SLA first call</h1>
            <p className="muted">Lead Mới → log call đầu tiên trong 15 phút (CRM-UC-008)</p>
          </div>
          <div className="row gap-sm">
            <Link href="/crm/leads" className="btn btn-secondary">
              Quản lý Lead
            </Link>
            <button type="button" className="btn btn-secondary" onClick={() => exportCsv()}>
              Export CSV
            </button>
          </div>
        </header>

        <div className="card" style={{ marginBottom: '1rem' }}>
          <div className="row gap-sm wrap">
            <label>
              SLA filter
              <select value={slaFilter} onChange={(e) => setSlaFilter(e.target.value as typeof slaFilter)}>
                <option value="breach">SLA breach</option>
                <option value="warning">Sắp breach</option>
                <option value="open">Đang mở (ok+warning)</option>
                <option value="all">Tất cả</option>
              </select>
            </label>
            <label>
              Owner ID
              <input value={ownerId} onChange={(e) => setOwnerId(e.target.value)} placeholder="optional" />
            </label>
            <label className="grow">
              Tìm kiếm
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Tên / SĐT / email" />
            </label>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => {
                setQuery(q.trim());
                void loadBoard(token, 0);
              }}
            >
              Lọc
            </button>
          </div>
          <p className="muted" style={{ marginTop: '0.75rem' }}>
            Tổng {summary.total} · Breach {summary.breach} · Warning {summary.warning} · OK {summary.ok}
          </p>
        </div>

        {canAssign ? (
          <div className="card" style={{ marginBottom: '1rem' }}>
            <h2 style={{ marginTop: 0, fontSize: '1rem' }}>Bulk actions ({selected.size} selected)</h2>
            <div className="row gap-sm wrap">
              <label>
                Reassign to
                <select value={assignTo} onChange={(e) => setAssignTo(e.target.value)}>
                  <option value="">— staff —</option>
                  {staffOptions.map((s) => (
                    <option key={s.id} value={String(s.id)}>
                      {s.name} (#{s.id})
                    </option>
                  ))}
                </select>
              </label>
              <label className="grow">
                Lý do
                <input value={assignReason} onChange={(e) => setAssignReason(e.target.value)} />
              </label>
              <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void runBulkAssign()}>
                Bulk reassign
              </button>
            </div>
            <div className="row gap-sm wrap" style={{ marginTop: '0.75rem' }}>
              <label>
                Follow-up at
                <input type="datetime-local" value={followUpAt} onChange={(e) => setFollowUpAt(e.target.value)} />
              </label>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={busy}
                onClick={() => void runBulkReschedule()}
              >
                Bulk reschedule
              </button>
            </div>
          </div>
        ) : null}

        {error ? <p className="error">{error}</p> : null}
        {msg ? <p className="ok-text">{msg}</p> : null}

        <div className="card table-wrap">
          {loading ? <p className="muted">Đang tải…</p> : null}
          <table className="data-table">
            <thead>
              <tr>
                {canAssign ? (
                  <th>
                    <input type="checkbox" checked={allSelected} onChange={toggleAll} aria-label="Chọn tất cả" />
                  </th>
                ) : null}
                <th>Lead</th>
                <th>Status</th>
                <th>Owner</th>
                <th>Received</th>
                <th>First call</th>
                <th>SLA</th>
                <th>Follow-up</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const badge = slaBadge(row.sla_state);
                return (
                  <tr key={row.id} className={row.sla_state === 'breach' ? 'row-danger' : undefined}>
                    {canAssign ? (
                      <td>
                        <input
                          type="checkbox"
                          checked={selected.has(row.id)}
                          onChange={() => toggleOne(row.id)}
                          aria-label={`Chọn lead ${row.id}`}
                        />
                      </td>
                    ) : null}
                    <td>
                      <Link href={`/crm/leads/${row.id}`}>{row.full_name || `#${row.id}`}</Link>
                      <div className="muted">{row.phone}</div>
                    </td>
                    <td>{row.status}</td>
                    <td>{row.owner_name ?? row.owner_id ?? '—'}</td>
                    <td>{row.received_at?.slice(0, 16) ?? '—'}</td>
                    <td>{row.first_call_at?.slice(0, 16) ?? '—'}</td>
                    <td>
                      <span className={badge.className}>{badge.label}</span>
                      {row.sla_minutes_elapsed != null ? (
                        <span className="muted"> · {row.sla_minutes_elapsed}m</span>
                      ) : null}
                    </td>
                    <td>{row.next_follow_up_at?.slice(0, 16) ?? '—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {!loading && rows.length === 0 ? <p className="muted">Không có lead phù hợp bộ lọc.</p> : null}
        </div>

        <div className="row gap-sm" style={{ marginTop: '1rem' }}>
          <button
            type="button"
            className="btn btn-secondary"
            disabled={offset <= 0 || loading}
            onClick={() => void loadBoard(token, Math.max(0, offset - PAGE_SIZE))}
          >
            ← Trước
          </button>
          <span className="muted">
            {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} / {total}
          </span>
          <button
            type="button"
            className="btn btn-secondary"
            disabled={offset + PAGE_SIZE >= total || loading}
            onClick={() => void loadBoard(token, offset + PAGE_SIZE)}
          >
            Sau →
          </button>
        </div>
      </div>
    </main>
  );
}
