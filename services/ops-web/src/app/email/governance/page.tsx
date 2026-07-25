'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  createEmailGovernanceRule,
  deleteEmailGovernanceRule,
  fetchEmailGovernance,
  patchEmailGovernanceRule,
  staffMe,
  staffRefresh,
  type EmailGovernanceResponse,
  type EmailGovernanceRule,
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

const RULE_TYPES = [
  'frequency_cap_7d',
  'quiet_hours',
  'complaint_rate_threshold',
  'approval_threshold_audience',
  'custom',
];

export default function EmailGovernancePage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [data, setData] = useState<EmailGovernanceResponse | null>(null);
  const [scope, setScope] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [editId, setEditId] = useState<string | null>(null);
  const [editConfig, setEditConfig] = useState('{}');
  const [newRule, setNewRule] = useState({ rule_type: 'custom', config_json: '{}', priority: 100 });

  const canWrite =
    Boolean(data?.can_write) ||
    (user ? hasCap(user, 'crm_email_mkt', 'settings') || hasCap(user, 'crm_agency', 'create') : false);

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
      if (!hasCap(me, 'crm_email_mkt', 'view') && !hasCap(me, 'crm_agency', 'view')) {
        setError('Không có quyền Email Marketing');
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

  const load = useCallback(
    async (access: string) => {
      setLoading(true);
      setError('');
      try {
        const out = await fetchEmailGovernance(access, { scope: scope.trim() || undefined });
        setData(out);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải governance thất bại');
      } finally {
        setLoading(false);
      }
    },
    [scope],
  );

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      await load(access);
    })();
  }, [ensureAuth, load]);

  async function toggleRule(rule: EmailGovernanceRule) {
    const access = getAccessToken();
    if (!access || !canWrite) return;
    await patchEmailGovernanceRule(access, rule.id, { enabled: !rule.enabled });
    await load(access);
  }

  async function saveEdit(ruleId: string) {
    const access = getAccessToken();
    if (!access) return;
    let parsed: Record<string, unknown> = {};
    try {
      parsed = JSON.parse(editConfig) as Record<string, unknown>;
    } catch {
      setError('Config JSON không hợp lệ');
      return;
    }
    await patchEmailGovernanceRule(access, ruleId, { config_json: parsed });
    setEditId(null);
    await load(access);
  }

  async function createRule() {
    const access = getAccessToken();
    if (!access) return;
    let parsed: Record<string, unknown> = {};
    try {
      parsed = JSON.parse(newRule.config_json) as Record<string, unknown>;
    } catch {
      setError('Config JSON không hợp lệ');
      return;
    }
    await createEmailGovernanceRule(access, {
      scope: 'global',
      rule_type: newRule.rule_type,
      config_json: parsed,
      priority: newRule.priority,
      enabled: true,
    });
    await load(access);
  }

  async function removeRule(ruleId: string) {
    const access = getAccessToken();
    if (!access || !window.confirm('Xóa rule này?')) return;
    await deleteEmailGovernanceRule(access, ruleId);
    await load(access);
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

  return (
    <main style={{ maxWidth: 1200, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <div className="card" style={{ marginBottom: '1rem' }}>
        <p className="muted" style={{ marginTop: 0 }}>
          E-13 Governance hub · {canWrite ? 'read/write' : 'read-only'}
        </p>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <Link href="/email/hub" className="btn btn-sm">← Email hub</Link>
          {!canWrite ? <span className="badge">Read-only</span> : null}
          <label className="muted">
            Scope{' '}
            <select value={scope} onChange={(e) => setScope(e.target.value)} style={{ marginLeft: '0.35rem' }}>
              <option value="">All</option>
              <option value="global">Global</option>
              <option value="brand">Brand</option>
              <option value="market">Market</option>
              <option value="client">Client</option>
            </select>
          </label>
          <button type="button" className="btn btn-secondary btn-sm" disabled={loading} onClick={() => { const a = getAccessToken(); if (a) void load(a); }}>
            Làm mới
          </button>
        </div>
      </div>

      {error ? <p className="error">{error}</p> : null}

      {canWrite ? (
        <div className="card" style={{ marginBottom: '1rem' }}>
          <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Thêm global rule</h2>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <label>
              Type
              <select value={newRule.rule_type} onChange={(e) => setNewRule({ ...newRule, rule_type: e.target.value })} style={{ display: 'block', marginTop: '0.25rem' }}>
                {RULE_TYPES.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </label>
            <label>
              Priority
              <input type="number" value={newRule.priority} onChange={(e) => setNewRule({ ...newRule, priority: Number(e.target.value) })} style={{ display: 'block', width: 80, marginTop: '0.25rem' }} />
            </label>
            <label style={{ flex: 1, minWidth: 240 }}>
              config_json
              <input value={newRule.config_json} onChange={(e) => setNewRule({ ...newRule, config_json: e.target.value })} style={{ display: 'block', width: '100%', marginTop: '0.25rem', fontFamily: 'monospace' }} />
            </label>
            <button type="button" className="btn btn-sm" onClick={() => void createRule()}>+ Thêm rule</button>
          </div>
        </div>
      ) : null}

      <div className="card" style={{ marginBottom: '1rem' }}>
        <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Global rules</h2>
        <div style={{ overflowX: 'auto' }}>
          <table className="perf-table">
            <thead>
              <tr>
                <th>Scope</th>
                <th>Type</th>
                <th>Config</th>
                <th>Priority</th>
                <th>Enabled</th>
                {canWrite ? <th /> : null}
              </tr>
            </thead>
            <tbody>
              {(data?.rules ?? []).map((rule) => (
                <tr key={rule.id}>
                  <td>{rule.scope}</td>
                  <td>{rule.rule_type}</td>
                  <td>
                    {editId === rule.id ? (
                      <textarea value={editConfig} onChange={(e) => setEditConfig(e.target.value)} rows={3} style={{ width: '100%', fontFamily: 'monospace', fontSize: '0.85rem' }} />
                    ) : (
                      <code style={{ fontSize: '0.85rem' }}>{JSON.stringify(rule.config_json)}</code>
                    )}
                  </td>
                  <td>{rule.priority}</td>
                  <td>
                    {canWrite ? (
                      <button type="button" className="btn btn-secondary btn-sm" onClick={() => void toggleRule(rule)}>
                        {rule.enabled ? '✓ ON' : '— OFF'}
                      </button>
                    ) : (
                      rule.enabled ? '✓' : '—'
                    )}
                  </td>
                  {canWrite ? (
                    <td style={{ whiteSpace: 'nowrap' }}>
                      {editId === rule.id ? (
                        <button type="button" className="btn btn-sm" onClick={() => void saveEdit(rule.id)}>Lưu</button>
                      ) : (
                        <button type="button" className="btn btn-secondary btn-sm" onClick={() => { setEditId(rule.id); setEditConfig(JSON.stringify(rule.config_json, null, 2)); }}>Sửa</button>
                      )}
                      {' '}
                      <button type="button" className="btn btn-secondary btn-sm" onClick={() => void removeRule(rule.id)}>Xóa</button>
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Audit log (50 gần nhất)</h2>
        <div style={{ overflowX: 'auto' }}>
          <table className="perf-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Actor</th>
                <th>Action</th>
                <th>Entity</th>
                <th>Diff</th>
              </tr>
            </thead>
            <tbody>
              {(data?.audit_log ?? []).map((row) => (
                <tr key={row.id}>
                  <td>{row.created_at ? row.created_at.slice(0, 19) : '—'}</td>
                  <td>{row.actor}</td>
                  <td>{row.action}</td>
                  <td>{row.entity_type}{row.entity_id ? ` · ${row.entity_id.slice(0, 8)}…` : ''}</td>
                  <td>
                    <code style={{ fontSize: '0.75rem' }}>
                      {row.before_json || row.after_json
                        ? `${row.before_json ? 'before' : ''}${row.before_json && row.after_json ? ' → ' : ''}${row.after_json ? 'after' : ''}`
                        : '—'}
                    </code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
