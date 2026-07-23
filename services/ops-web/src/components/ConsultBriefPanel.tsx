'use client';

import { useCallback, useEffect, useState } from 'react';
import { fetchServiceLifecycleConsultBrief, postServiceLifecycleConsultPrefill } from '@/lib/api';
import { hasCap, type StoredStaffUser } from '@/lib/auth';

type ConsultBrief = {
  service_label?: string;
  readiness?: {
    lead_task_done?: boolean;
    has_any_intake?: boolean;
    decision_label?: string;
    bant_total?: number;
    temperature_label?: string;
    consult_gate_level?: string;
  };
  highlights?: {
    pain?: string;
    niche?: string;
    domain?: string;
    goal?: string;
    budget_vnd?: number | null;
  };
  latest_intake_summary?: string;
  recommended_actions?: string[];
  red_flags?: string[];
};

interface Props {
  token: string;
  user: StoredStaffUser;
  lifecycleId: number;
  onPrefilled?: () => void;
}

function gateColor(level: string | undefined): string {
  if (level === 'ok') return 'var(--accent)';
  if (level === 'block') return 'var(--error, #c44)';
  return '#c90';
}

export function ConsultBriefPanel({ token, user, lifecycleId, onPrefilled }: Props) {
  const [brief, setBrief] = useState<ConsultBrief | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [overwrite, setOverwrite] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const canEdit = hasCap(user, 'crm_board', 'edit');

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const out = await fetchServiceLifecycleConsultBrief(token, lifecycleId);
      setBrief(out as ConsultBrief);
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tải consult brief thất bại');
    } finally {
      setLoading(false);
    }
  }, [token, lifecycleId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function onPrefill() {
    if (!canEdit) return;
    setSaving(true);
    setMessage('');
    setError('');
    try {
      const out = await postServiceLifecycleConsultPrefill(token, lifecycleId, { overwrite });
      setMessage(`Prefill: ${Number(out.filled ?? 0)} field · ${(out.fields as string[] | undefined)?.join(', ') || '—'}`);
      onPrefilled?.();
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Prefill thất bại');
    } finally {
      setSaving(false);
    }
  }

  const readiness = brief?.readiness ?? {};
  const highlights = brief?.highlights ?? {};

  return (
    <aside className="card" style={{ padding: '1rem', display: 'grid', gap: '0.75rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem' }}>
        <h3 style={{ margin: 0, fontSize: '1rem' }}>Consult Brief</h3>
        <span style={{ color: gateColor(readiness.consult_gate_level), fontSize: '0.85rem', fontWeight: 600 }}>
          {readiness.consult_gate_level?.toUpperCase() ?? '—'}
        </span>
      </div>

      {loading ? <p className="muted">Đang tải…</p> : null}
      {error ? <p className="error">{error}</p> : null}
      {message ? <p style={{ color: 'var(--accent)' }}>{message}</p> : null}

      {brief ? (
        <>
          <p className="muted" style={{ margin: 0 }}>
            {brief.service_label ?? ''} · Decision {readiness.decision_label ?? '—'} · BANT{' '}
            {readiness.bant_total ?? 0}/30 · {readiness.temperature_label ?? '—'}
          </p>

          <ul style={{ margin: 0, paddingLeft: '1.1rem', fontSize: '0.9rem' }}>
            <li>Task Lead: {readiness.lead_task_done ? '✓' : '—'}</li>
            <li>Intake: {readiness.has_any_intake ? '✓' : '—'}</li>
          </ul>

          {(highlights.pain || highlights.niche || highlights.domain) ? (
            <div style={{ fontSize: '0.9rem' }}>
              {highlights.pain ? <p style={{ margin: '0 0 0.35rem' }}><strong>Pain:</strong> {highlights.pain}</p> : null}
              {highlights.niche ? <p style={{ margin: '0 0 0.35rem' }}><strong>Ngành:</strong> {highlights.niche}</p> : null}
              {highlights.domain ? <p style={{ margin: '0 0 0.35rem' }}><strong>Domain:</strong> {highlights.domain}</p> : null}
            </div>
          ) : null}

          {brief.latest_intake_summary ? (
            <div>
              <span className="muted">Tóm tắt intake</span>
              <p style={{ margin: '0.25rem 0 0', fontSize: '0.9rem', whiteSpace: 'pre-wrap' }}>
                {brief.latest_intake_summary}
              </p>
            </div>
          ) : null}

          {(brief.recommended_actions?.length ?? 0) > 0 ? (
            <div>
              <span className="muted">Gợi ý</span>
              <ul style={{ margin: '0.25rem 0 0', paddingLeft: '1.1rem', fontSize: '0.9rem' }}>
                {brief.recommended_actions!.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {(brief.red_flags?.length ?? 0) > 0 ? (
            <div>
              <span className="error">Red flags</span>
              <ul className="error" style={{ margin: '0.25rem 0 0', paddingLeft: '1.1rem', fontSize: '0.9rem' }}>
                {brief.red_flags!.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {canEdit ? (
            <div style={{ display: 'grid', gap: '0.5rem' }}>
              <label style={{ display: 'flex', gap: '0.4rem', alignItems: 'center', fontSize: '0.9rem' }}>
                <input type="checkbox" checked={overwrite} onChange={(e) => setOverwrite(e.target.checked)} />
                Ghi đè field đã có
              </label>
              <button type="button" className="btn btn-sm btn-secondary" disabled={saving} onClick={() => void onPrefill()}>
                Prefill từ Lead / Intake
              </button>
            </div>
          ) : null}
        </>
      ) : null}
    </aside>
  );
}
