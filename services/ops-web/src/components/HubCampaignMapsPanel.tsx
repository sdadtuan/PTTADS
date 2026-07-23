'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import {
  createClientHubCampaignMap,
  createHubCampaignMap,
  deleteClientHubCampaignMap,
  deleteHubCampaignMap,
  fetchAgencyClients,
  fetchClientHubCampaignMaps,
  fetchHubCampaignMaps,
  updateClientHubCampaignMap,
  updateHubCampaignMap,
  type AgencyClient,
  type HubMapRow,
} from '@/lib/api';

function normalizeMetaId(raw: string): string {
  return raw.replace(/\D/g, '').trim();
}

function fmtVnd(n: number | null | undefined): string {
  if (n == null) return '—';
  return Math.round(n).toLocaleString('vi-VN') + ' ₫';
}

const EMPTY_CREATE = {
  client_id: '',
  channel: 'meta',
  external_campaign_id: '',
  external_campaign_name: '',
  external_account_id: '',
  target_cpl_vnd: '',
};

const EMPTY_EDIT = {
  external_campaign_id: '',
  external_campaign_name: '',
  external_account_id: '',
  target_cpl_vnd: '',
  active: true,
};

export interface HubCampaignMapsPanelProps {
  token: string;
  canWrite: boolean;
  /** Client-scoped mode — hides client picker */
  clientId?: string;
  clientLabel?: string;
  /** Global hub page — show client column + picker on create */
  showClientColumn?: boolean;
  /** Pre-filter global list */
  filterClientId?: string;
  filterCampaignId?: string;
  onFeedback?: (msg: string) => void;
  onError?: (msg: string) => void;
}

export function HubCampaignMapsPanel({
  token,
  canWrite,
  clientId,
  clientLabel,
  showClientColumn = false,
  filterClientId,
  filterCampaignId,
  onFeedback,
  onError,
}: HubCampaignMapsPanelProps) {
  const scoped = Boolean(clientId);
  const [maps, setMaps] = useState<HubMapRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [clients, setClients] = useState<AgencyClient[]>([]);
  const [createForm, setCreateForm] = useState({ ...EMPTY_CREATE, client_id: clientId ?? filterClientId ?? '' });
  const [editMapId, setEditMapId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState(EMPTY_EDIT);
  const [showInactive, setShowInactive] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      if (scoped && clientId) {
        const out = await fetchClientHubCampaignMaps(token, clientId, {
          include_inactive: showInactive,
        });
        setMaps(out.maps);
      } else {
        const out = await fetchHubCampaignMaps(token, {
          client_id: filterClientId || undefined,
          campaign_id: filterCampaignId || undefined,
        });
        setMaps(out.maps);
      }
    } catch (err) {
      onError?.(err instanceof Error ? err.message : 'Tải campaign map thất bại');
    } finally {
      setLoading(false);
    }
  }, [token, scoped, clientId, showInactive, filterClientId, filterCampaignId, onError]);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    if (!showClientColumn || scoped || !canWrite) return;
    void (async () => {
      try {
        const out = await fetchAgencyClients(token, { status: 'active' });
        setClients(out.clients ?? []);
      } catch {
        /* optional picker */
      }
    })();
  }, [token, showClientColumn, scoped, canWrite]);

  function validateCreate(): string | null {
    const ch = createForm.channel.trim().toLowerCase();
    const ext =
      ch === 'meta'
        ? normalizeMetaId(createForm.external_campaign_id)
        : createForm.external_campaign_id.trim();
    if (!scoped && !createForm.client_id.trim()) return 'Chọn client';
    if (!ext) return 'Nhập Campaign ID';
    if (ch === 'meta' && !/^[0-9]{5,20}$/.test(ext)) {
      return 'Meta Campaign ID phải là số 5–20 chữ số';
    }
    return null;
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!canWrite) return;
    const errMsg = validateCreate();
    if (errMsg) {
      onError?.(errMsg);
      return;
    }
    setBusy(true);
    onError?.('');
    try {
      const ch = createForm.channel.trim().toLowerCase();
      const externalId =
        ch === 'meta'
          ? normalizeMetaId(createForm.external_campaign_id)
          : createForm.external_campaign_id.trim();
      const body = {
        channel: ch,
        external_campaign_id: externalId,
        external_campaign_name: createForm.external_campaign_name.trim() || undefined,
        external_account_id: createForm.external_account_id.trim() || undefined,
        target_cpl_vnd: createForm.target_cpl_vnd
          ? Number(createForm.target_cpl_vnd.replace(/\D/g, ''))
          : undefined,
      };
      let jobsNote = '';
      if (scoped && clientId) {
        const out = await createClientHubCampaignMap(token, clientId, body);
        if (out.jobs_enqueued?.length) jobsNote = ` · đã enqueue ${out.jobs_enqueued.length} job sync`;
      } else {
        const out = await createHubCampaignMap(token, {
          ...body,
          client_id: createForm.client_id.trim(),
        });
        if (out.jobs_enqueued?.length) jobsNote = ` · đã enqueue ${out.jobs_enqueued.length} job sync`;
      }
      setCreateForm({
        ...EMPTY_CREATE,
        client_id: clientId ?? filterClientId ?? createForm.client_id,
      });
      onFeedback?.(`Đã thêm campaign map${jobsNote}`);
      await reload();
    } catch (err) {
      onError?.(err instanceof Error ? err.message : 'Thêm map thất bại');
    } finally {
      setBusy(false);
    }
  }

  function startEdit(row: HubMapRow) {
    if (!row.map_id) return;
    setEditMapId(row.map_id);
    setEditForm({
      external_campaign_id: row.external_campaign_id ?? '',
      external_campaign_name: row.external_campaign_name ?? '',
      external_account_id: row.external_account_id ?? '',
      target_cpl_vnd: row.target_cpl_vnd != null ? String(Math.round(row.target_cpl_vnd)) : '',
      active: row.active,
    });
  }

  async function handleUpdate(e: React.FormEvent) {
    e.preventDefault();
    if (!canWrite || !editMapId) return;
    const row = maps.find((m) => m.map_id === editMapId);
    const ch = row?.channel ?? 'meta';
    const externalId =
      ch === 'meta' ? normalizeMetaId(editForm.external_campaign_id) : editForm.external_campaign_id.trim();
    if (ch === 'meta' && !/^[0-9]{5,20}$/.test(externalId)) {
      onError?.('Meta Campaign ID phải là số 5–20 chữ số');
      return;
    }
    setBusy(true);
    onError?.('');
    try {
      const body = {
        external_campaign_id: externalId,
        external_campaign_name: editForm.external_campaign_name.trim() || null,
        external_account_id: editForm.external_account_id.trim() || null,
        target_cpl_vnd: editForm.target_cpl_vnd
          ? Number(editForm.target_cpl_vnd.replace(/\D/g, ''))
          : null,
        active: editForm.active,
      };
      const cid = scoped ? clientId : row?.client_id;
      if (scoped && clientId) {
        await updateClientHubCampaignMap(token, clientId, editMapId, body);
      } else {
        await updateHubCampaignMap(token, editMapId, body, cid);
      }
      setEditMapId(null);
      onFeedback?.('Đã cập nhật campaign map');
      await reload();
    } catch (err) {
      onError?.(err instanceof Error ? err.message : 'Cập nhật thất bại');
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(row: HubMapRow) {
    if (!canWrite || !row.map_id) return;
    const label = row.external_campaign_name || row.external_campaign_id || row.map_id;
    if (!window.confirm(`Xóa map campaign "${label}"? Hành động không hoàn tác.`)) return;
    setBusy(true);
    onError?.('');
    try {
      if (scoped && clientId) {
        await deleteClientHubCampaignMap(token, clientId, row.map_id);
      } else {
        await deleteHubCampaignMap(token, row.map_id, row.client_id);
      }
      if (editMapId === row.map_id) setEditMapId(null);
      onFeedback?.('Đã xóa campaign map');
      await reload();
    } catch (err) {
      onError?.(err instanceof Error ? err.message : 'Xóa thất bại');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <p className="muted" style={{ marginTop: 0 }}>
        {scoped
          ? `Map campaign Meta/Google/Zalo cho client ${clientLabel ?? ''}. Sau khi thêm map, hệ thống tự enqueue sync insights (nếu PTT_JOBS_ENABLED=1).`
          : 'Quản lý hub campaign map trên PostgreSQL — không cần sync từ SQLite Hub.'}
      </p>

      {scoped ? (
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
          <input
            type="checkbox"
            checked={showInactive}
            onChange={(e) => setShowInactive(e.target.checked)}
          />
          Hiện map đã tắt (inactive)
        </label>
      ) : null}

      {canWrite ? (
        <form
          onSubmit={(e) => void handleCreate(e)}
          style={{
            display: 'grid',
            gap: '0.65rem',
            maxWidth: 560,
            marginBottom: '1.25rem',
            padding: '1rem',
            border: '1px solid var(--border, #e2e8f0)',
            borderRadius: 8,
          }}
        >
          <h3 style={{ fontSize: '1rem', margin: 0 }}>Thêm campaign map</h3>
          {showClientColumn && !scoped ? (
            <label>
              Client
              <select
                value={createForm.client_id}
                onChange={(e) => setCreateForm((f) => ({ ...f, client_id: e.target.value }))}
                required
                style={{ width: '100%', padding: '0.5rem' }}
              >
                <option value="">— Chọn client —</option>
                {clients.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.code} · {c.name}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <label>
            Kênh
            <select
              value={createForm.channel}
              onChange={(e) => setCreateForm((f) => ({ ...f, channel: e.target.value }))}
              style={{ width: '100%', padding: '0.5rem' }}
            >
              <option value="meta">Meta</option>
              <option value="google">Google</option>
              <option value="zalo">Zalo</option>
            </select>
          </label>
          <label>
            Campaign ID (Meta: số từ Ads Manager)
            <input
              value={createForm.external_campaign_id}
              onChange={(e) => setCreateForm((f) => ({ ...f, external_campaign_id: e.target.value }))}
              placeholder="120250314265080598"
              required
              style={{ width: '100%', padding: '0.5rem' }}
            />
          </label>
          <label>
            Tên campaign (tuỳ chọn)
            <input
              value={createForm.external_campaign_name}
              onChange={(e) => setCreateForm((f) => ({ ...f, external_campaign_name: e.target.value }))}
              style={{ width: '100%', padding: '0.5rem' }}
            />
          </label>
          <label>
            Ad account ID (tuỳ chọn — mặc định lấy từ kênh Meta)
            <input
              value={createForm.external_account_id}
              onChange={(e) => setCreateForm((f) => ({ ...f, external_account_id: e.target.value }))}
              placeholder="act_2101678607367558"
              style={{ width: '100%', padding: '0.5rem' }}
            />
          </label>
          <label>
            Target CPL (VND)
            <input
              value={createForm.target_cpl_vnd}
              onChange={(e) => setCreateForm((f) => ({ ...f, target_cpl_vnd: e.target.value }))}
              placeholder="150000"
              style={{ width: '100%', padding: '0.5rem' }}
            />
          </label>
          <button type="submit" className="btn btn-sm" disabled={busy}>
            Thêm map
          </button>
        </form>
      ) : null}

      {editMapId && canWrite ? (
        <form
          onSubmit={(e) => void handleUpdate(e)}
          style={{
            display: 'grid',
            gap: '0.65rem',
            maxWidth: 560,
            marginBottom: '1.25rem',
            padding: '1rem',
            border: '1px solid var(--accent, #6366f1)',
            borderRadius: 8,
          }}
        >
          <h3 style={{ fontSize: '1rem', margin: 0 }}>Sửa campaign map</h3>
          <label>
            Campaign ID
            <input
              value={editForm.external_campaign_id}
              onChange={(e) => setEditForm((f) => ({ ...f, external_campaign_id: e.target.value }))}
              required
              style={{ width: '100%', padding: '0.5rem' }}
            />
          </label>
          <label>
            Tên campaign
            <input
              value={editForm.external_campaign_name}
              onChange={(e) => setEditForm((f) => ({ ...f, external_campaign_name: e.target.value }))}
              style={{ width: '100%', padding: '0.5rem' }}
            />
          </label>
          <label>
            Ad account ID
            <input
              value={editForm.external_account_id}
              onChange={(e) => setEditForm((f) => ({ ...f, external_account_id: e.target.value }))}
              style={{ width: '100%', padding: '0.5rem' }}
            />
          </label>
          <label>
            Target CPL (VND)
            <input
              value={editForm.target_cpl_vnd}
              onChange={(e) => setEditForm((f) => ({ ...f, target_cpl_vnd: e.target.value }))}
              style={{ width: '100%', padding: '0.5rem' }}
            />
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <input
              type="checkbox"
              checked={editForm.active}
              onChange={(e) => setEditForm((f) => ({ ...f, active: e.target.checked }))}
            />
            Đang active (bỏ tick = tạm ẩn, không xóa)
          </label>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button type="submit" className="btn btn-sm" disabled={busy}>
              Lưu thay đổi
            </button>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => setEditMapId(null)}>
              Hủy
            </button>
          </div>
        </form>
      ) : null}

      {loading ? <p className="muted">Đang tải map…</p> : null}

      <div style={{ overflowX: 'auto' }}>
        <table className="perf-table">
          <thead>
            <tr>
              {showClientColumn && !scoped ? <th>Client</th> : null}
              <th>Hub ID</th>
              <th>Kênh</th>
              <th>Tên</th>
              <th>Campaign ID</th>
              <th>Ad account</th>
              <th>Target CPL</th>
              <th>Trạng thái</th>
              {canWrite ? <th /> : null}
            </tr>
          </thead>
          <tbody>
            {maps.map((m) => (
              <tr key={m.map_id ?? `${m.client_id}-${m.external_campaign_id}`} style={m.active ? undefined : { opacity: 0.65 }}>
                {showClientColumn && !scoped ? (
                  <td>
                    {m.client_id ? (
                      <Link href={`/agency/clients/${m.client_id}?tab=campaigns`} className="nav-link">
                        {m.client_code || m.client_name || m.client_id.slice(0, 8)}
                      </Link>
                    ) : (
                      '—'
                    )}
                  </td>
                ) : null}
                <td>{m.hub_campaign_id ?? '—'}</td>
                <td>{m.channel}</td>
                <td>{m.external_campaign_name || '—'}</td>
                <td>{m.external_campaign_id || '—'}</td>
                <td>{m.external_account_id || '—'}</td>
                <td>{fmtVnd(m.target_cpl_vnd)}</td>
                <td>{m.active ? 'active' : 'inactive'}</td>
                {canWrite ? (
                  <td style={{ whiteSpace: 'nowrap' }}>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      disabled={busy || !m.map_id}
                      onClick={() => startEdit(m)}
                    >
                      Sửa
                    </button>{' '}
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      disabled={busy || !m.map_id}
                      onClick={() => void handleDelete(m)}
                    >
                      Xóa
                    </button>
                  </td>
                ) : null}
              </tr>
            ))}
            {!loading && maps.length === 0 ? (
              <tr>
                <td colSpan={showClientColumn && !scoped ? 9 : 8} className="muted">
                  Chưa có campaign map — dùng form phía trên để thêm (không cần SQLite sync).
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
