'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  createClientPortalUser,
  fetchClientPortalUsers,
  patchClientPortalUser,
  resetClientPortalUserPassword,
  type PortalClientUser,
} from '@/lib/api';

type Props = {
  token: string;
  clientId: string;
  canMutate: boolean;
  onMessage?: (msg: string) => void;
  onError?: (msg: string) => void;
};

function fmtDate(value: string | null): string {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleString('vi-VN');
  } catch {
    return value;
  }
}

export function ClientPortalUsersPanel({ token, clientId, canMutate, onMessage, onError }: Props) {
  const [users, setUsers] = useState<PortalClientUser[]>([]);
  const [tableReady, setTableReady] = useState(true);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [revealedPassword, setRevealedPassword] = useState<string | null>(null);
  const [form, setForm] = useState({ email: '', password: '', role: 'viewer' as 'viewer' | 'approver' });

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const out = await fetchClientPortalUsers(token, clientId);
      setUsers(out.users ?? []);
      setTableReady(out.table_ready !== false);
    } catch (err) {
      onError?.(err instanceof Error ? err.message : 'Tải portal users thất bại');
      setUsers([]);
    } finally {
      setLoading(false);
    }
  }, [token, clientId, onError]);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!canMutate) return;
    setBusy(true);
    setRevealedPassword(null);
    onError?.('');
    try {
      const body: { email: string; role: 'viewer' | 'approver'; password?: string } = {
        email: form.email.trim(),
        role: form.role,
      };
      if (form.password.trim()) {
        body.password = form.password.trim();
      }
      const out = await createClientPortalUser(token, clientId, body);
      if (out.temporary_password) {
        setRevealedPassword(out.temporary_password);
        onMessage?.(
          `Đã tạo portal user ${out.user.email}. Sao chép mật khẩu tạm bên dưới — chỉ hiển thị một lần.`,
        );
      } else {
        onMessage?.(`Đã tạo portal user ${out.user.email}`);
      }
      setForm({ email: '', password: '', role: 'viewer' });
      await reload();
    } catch (err) {
      onError?.(err instanceof Error ? err.message : 'Tạo portal user thất bại');
    } finally {
      setBusy(false);
    }
  }

  async function handleToggleActive(user: PortalClientUser) {
    if (!canMutate) return;
    const next = !user.active;
    const label = next ? 'kích hoạt lại' : 'vô hiệu hoá';
    if (!window.confirm(`${label} portal user ${user.email}?`)) return;
    setBusy(true);
    onError?.('');
    try {
      await patchClientPortalUser(token, clientId, user.id, { active: next });
      onMessage?.(`Đã ${label} ${user.email}`);
      await reload();
    } catch (err) {
      onError?.(err instanceof Error ? err.message : 'Cập nhật portal user thất bại');
    } finally {
      setBusy(false);
    }
  }

  async function handleRoleChange(user: PortalClientUser, role: 'viewer' | 'approver') {
    if (!canMutate || user.role === role) return;
    setBusy(true);
    onError?.('');
    try {
      await patchClientPortalUser(token, clientId, user.id, { role });
      onMessage?.(`Đã đổi role ${user.email} → ${role}`);
      await reload();
    } catch (err) {
      onError?.(err instanceof Error ? err.message : 'Đổi role thất bại');
    } finally {
      setBusy(false);
    }
  }

  async function handleResetPassword(user: PortalClientUser) {
    if (!canMutate) return;
    if (!window.confirm(`Reset mật khẩu cho ${user.email}? Mật khẩu mới sẽ hiển thị một lần.`)) return;
    setBusy(true);
    setRevealedPassword(null);
    onError?.('');
    try {
      const out = await resetClientPortalUserPassword(token, clientId, user.id, {});
      if (out.temporary_password) {
        setRevealedPassword(out.temporary_password);
        onMessage?.(`Mật khẩu mới cho ${user.email} — sao chép ngay (vault/handover A4).`);
      } else {
        onMessage?.(`Đã reset mật khẩu ${user.email}`);
      }
    } catch (err) {
      onError?.(err instanceof Error ? err.message : 'Reset mật khẩu thất bại');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="portal-users-panel">
      <p className="muted" style={{ marginTop: 0 }}>
        Tài khoản đăng nhập{' '}
        <a href="https://portal.pttads.vn/login" target="_blank" rel="noreferrer">
          portal.pttads.vn
        </a>
        . Ghi mật khẩu lên form bàn giao credentials — không gửi plain text qua email.
      </p>

      {!tableReady ? (
        <p className="error">
          Bảng <code>portal_client_users</code> chưa có trên DB — chạy migration DDL Sprint 0 trước.
        </p>
      ) : null}

      {revealedPassword ? (
        <div
          className="card"
          style={{
            padding: '0.75rem 1rem',
            marginBottom: '1rem',
            borderColor: 'var(--accent)',
            background: 'rgba(255, 193, 7, 0.08)',
          }}
        >
          <strong>Mật khẩu tạm (hiển thị một lần)</strong>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginTop: '0.5rem', flexWrap: 'wrap' }}>
            <code style={{ fontSize: '1.1rem', userSelect: 'all' }}>{revealedPassword}</code>
            <button
              type="button"
              className="btn btn-sm"
              onClick={() => {
                void navigator.clipboard.writeText(revealedPassword);
                onMessage?.('Đã copy mật khẩu vào clipboard');
              }}
            >
              Copy
            </button>
            <button type="button" className="btn btn-sm btn-muted" onClick={() => setRevealedPassword(null)}>
              Ẩn
            </button>
          </div>
        </div>
      ) : null}

      {canMutate && tableReady ? (
        <form className="agency-client-edit" onSubmit={(e) => void handleCreate(e)} style={{ marginBottom: '1.25rem' }}>
          <h3 style={{ margin: '0 0 0.75rem', fontSize: '1rem' }}>+ Tạo portal user</h3>
          <label>
            Email
            <input
              type="email"
              value={form.email}
              onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              required
              placeholder="viewer@client.com"
            />
          </label>
          <label>
            Mật khẩu (để trống = tự sinh)
            <input
              type="text"
              value={form.password}
              onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
              placeholder="min 8 ký tự hoặc auto-generate"
              autoComplete="new-password"
            />
          </label>
          <label>
            Vai trò
            <select value={form.role} onChange={(e) => setForm((f) => ({ ...f, role: e.target.value as 'viewer' | 'approver' }))}>
              <option value="viewer">Viewer — xem báo cáo</option>
              <option value="approver">Approver — xem + duyệt</option>
            </select>
          </label>
          <div>
            <button type="submit" className="btn btn-sm" disabled={busy}>
              Tạo user
            </button>
          </div>
        </form>
      ) : null}

      <h3 style={{ fontSize: '1rem', margin: '0 0 0.5rem' }}>Danh sách ({users.length})</h3>
      {loading ? <p className="muted">Đang tải…</p> : null}
      {!loading && users.length === 0 ? <p className="muted">Chưa có portal user cho client này.</p> : null}
      {!loading && users.length > 0 ? (
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table" style={{ width: '100%', fontSize: '0.9rem' }}>
            <thead>
              <tr>
                <th>Email</th>
                <th>Role</th>
                <th>Trạng thái</th>
                <th>Login cuối</th>
                {canMutate ? <th>Thao tác</th> : null}
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td>{user.email}</td>
                  <td>
                    {canMutate ? (
                      <select
                        value={user.role}
                        disabled={busy}
                        onChange={(e) => void handleRoleChange(user, e.target.value as 'viewer' | 'approver')}
                      >
                        <option value="viewer">viewer</option>
                        <option value="approver">approver</option>
                      </select>
                    ) : (
                      user.role
                    )}
                  </td>
                  <td>
                    <span className={`agency-status-badge ${user.active ? 'badge-active' : 'badge-paused'}`}>
                      {user.active ? 'active' : 'inactive'}
                    </span>
                  </td>
                  <td className="muted">{fmtDate(user.last_login_at)}</td>
                  {canMutate ? (
                    <td style={{ whiteSpace: 'nowrap' }}>
                      <button type="button" className="btn btn-sm" disabled={busy} onClick={() => void handleResetPassword(user)}>
                        Reset MK
                      </button>{' '}
                      <button type="button" className="btn btn-sm btn-muted" disabled={busy} onClick={() => void handleToggleActive(user)}>
                        {user.active ? 'Vô hiệu' : 'Kích hoạt'}
                      </button>
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
