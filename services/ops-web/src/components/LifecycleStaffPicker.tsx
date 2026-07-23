'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { fetchCrmStaffList, patchServiceLifecycle, type CrmStaffRow } from '@/lib/api';
import { hasCap, type StoredStaffUser } from '@/lib/auth';

type ContextShape = {
  lead?: { owner_id?: number | null; owner_name?: string };
  presales?: { assigned_sp?: number | null; assigned_sp_name?: string };
};

type Props = {
  token: string;
  user: StoredStaffUser;
  lifecycleId: number;
  assignedAm: number | null;
  assignedSp: number | null;
  context?: ContextShape | null;
  onSaved?: () => void;
  onError?: (msg: string) => void;
};

export function LifecycleStaffPicker({
  token,
  user,
  lifecycleId,
  assignedAm,
  assignedSp,
  context,
  onSaved,
  onError,
}: Props) {
  const canEdit = hasCap(user, 'crm_board', 'edit');
  const [staff, setStaff] = useState<CrmStaffRow[]>([]);
  const [amId, setAmId] = useState('');
  const [spId, setSpId] = useState('');
  const [saving, setSaving] = useState(false);

  const defaultAm = context?.lead?.owner_id ?? assignedAm;
  const defaultSp = context?.presales?.assigned_sp ?? assignedSp;

  useEffect(() => {
    setAmId(defaultAm != null && defaultAm > 0 ? String(defaultAm) : '');
    setSpId(defaultSp != null && defaultSp > 0 ? String(defaultSp) : '');
  }, [defaultAm, defaultSp]);

  useEffect(() => {
    void (async () => {
      try {
        const out = await fetchCrmStaffList(token);
        setStaff(out.staff.filter((s) => s.active !== 0));
      } catch {
        /* optional */
      }
    })();
  }, [token]);

  const staffLabel = useCallback(
    (id: string) => {
      const row = staff.find((s) => String(s.id) === id);
      if (row) return `${row.name}${row.email ? ` (${row.email})` : ''}`;
      if (id && context?.lead?.owner_name && String(defaultAm) === id) return context.lead.owner_name;
      if (id && context?.presales?.assigned_sp_name && String(defaultSp) === id) {
        return context.presales.assigned_sp_name;
      }
      return id ? `#${id}` : '— Chọn —';
    },
    [staff, context, defaultAm, defaultSp],
  );

  const suggestedSp = useMemo(() => {
    if (defaultSp) return String(defaultSp);
    return '';
  }, [defaultSp]);

  async function save() {
    if (!canEdit) return;
    setSaving(true);
    try {
      await patchServiceLifecycle(token, lifecycleId, {
        assigned_am: amId ? Number(amId) : null,
        assigned_sp: spId ? Number(spId) : null,
      });
      onSaved?.();
    } catch (err) {
      onError?.(err instanceof Error ? err.message : 'Lưu AM/SP thất bại');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="card" style={{ padding: '1rem', marginBottom: '1rem' }}>
      <h3 style={{ margin: '0 0 0.5rem', fontSize: '1rem' }}>Phân công AM / SP</h3>
      <p className="muted" style={{ margin: '0 0 0.65rem', fontSize: '0.85rem' }}>
        AM gợi ý: lead owner{context?.lead?.owner_name ? ` (${context.lead.owner_name})` : ''}
        {suggestedSp ? ` · SP gợi ý presales: ${staffLabel(suggestedSp)}` : ''}
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: '0.65rem', alignItems: 'end' }}>
        <label style={{ display: 'grid', gap: '0.3rem' }}>
          <span className="muted">Account Manager</span>
          <select
            value={amId}
            disabled={!canEdit || saving}
            onChange={(e) => setAmId(e.target.value)}
            style={{
              background: 'var(--bg)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: '0.5rem',
              color: 'var(--text)',
            }}
          >
            <option value="">— Chọn AM —</option>
            {staff.map((s) => (
              <option key={s.id} value={String(s.id)}>
                {s.name} {s.email ? `· ${s.email}` : ''}
              </option>
            ))}
          </select>
        </label>
        <label style={{ display: 'grid', gap: '0.3rem' }}>
          <span className="muted">Service Provider</span>
          <select
            value={spId}
            disabled={!canEdit || saving}
            onChange={(e) => setSpId(e.target.value)}
            style={{
              background: 'var(--bg)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: '0.5rem',
              color: 'var(--text)',
            }}
          >
            <option value="">— Chọn SP —</option>
            {staff.map((s) => (
              <option key={s.id} value={String(s.id)}>
                {s.name} {s.email ? `· ${s.email}` : ''}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="btn btn-sm" disabled={!canEdit || saving} onClick={() => void save()}>
          Lưu
        </button>
      </div>
    </div>
  );
}
