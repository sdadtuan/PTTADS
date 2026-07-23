'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { fetchServiceLifecycleOnboardingBrief } from '@/lib/api';
import { hasCap, type StoredStaffUser } from '@/lib/auth';

type BriefPayload = {
  lifecycle_id: number;
  has_context: boolean;
  client_id: string | null;
  client_code?: string | null;
  client_name?: string | null;
  client_status?: string | null;
  progress: { total: number; completed: number; percent: number };
  incomplete_preview?: string[];
  workflow?: {
    status: string;
    found: boolean;
    temporal_enabled: boolean;
  } | null;
  links: {
    agency_checklist: string | null;
  };
  gate: {
    ok: boolean;
    warn_only?: boolean;
    progress_percent?: number;
    messages: string[];
  };
  message?: string | null;
};

type Props = {
  token: string;
  user: StoredStaffUser;
  lifecycleId: number;
  stage: string;
};

export function LifecycleOnboardingPanel({ token, user, lifecycleId, stage }: Props) {
  const canView = hasCap(user, 'crm_board', 'view');
  const [brief, setBrief] = useState<BriefPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const reload = useCallback(async () => {
    if (!canView) return;
    setLoading(true);
    setError('');
    try {
      const out = (await fetchServiceLifecycleOnboardingBrief(token, lifecycleId)) as BriefPayload;
      setBrief(out);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tải onboarding brief thất bại');
      setBrief(null);
    } finally {
      setLoading(false);
    }
  }, [token, lifecycleId, canView]);

  useEffect(() => {
    void reload();
  }, [reload]);

  if (!canView || stage !== 'onboard') return null;
  if (loading && !brief) {
    return (
      <div className="card" style={{ padding: '1rem', marginBottom: '1rem' }}>
        <p className="muted" style={{ margin: 0 }}>
          Đang tải checklist client…
        </p>
      </div>
    );
  }
  if (error) {
    return (
      <div className="card" style={{ padding: '1rem', marginBottom: '1rem' }}>
        <p className="error" style={{ margin: 0 }}>
          {error}
        </p>
      </div>
    );
  }
  if (!brief) return null;

  const showWarn = !brief.gate.ok && brief.gate.messages.length > 0;
  const checklistLink = brief.links.agency_checklist;

  return (
    <div
      className="card onboarding-lifecycle-panel"
      style={{
        padding: '1rem',
        marginBottom: '1rem',
        borderColor: showWarn ? 'var(--accent)' : undefined,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem', flexWrap: 'wrap' }}>
        <div>
          <h3 style={{ margin: 0, fontSize: '1rem' }}>Checklist agency client</h3>
          <p className="muted" style={{ margin: '0.35rem 0 0' }}>
            {brief.has_context && brief.client_name
              ? `${brief.client_name}${brief.client_code ? ` (${brief.client_code})` : ''} · ${brief.client_status ?? '—'}`
              : brief.message ?? 'Chưa liên kết agency client'}
          </p>
        </div>
        {brief.has_context ? (
          <span className="muted" style={{ fontWeight: 600 }}>
            {brief.progress.percent}% · {brief.progress.completed}/{brief.progress.total}
          </span>
        ) : null}
      </div>

      {showWarn ? (
        <div style={{ marginTop: '0.75rem' }}>
          <p className="error" style={{ margin: '0 0 0.35rem', fontWeight: 600 }}>
            Checklist client chưa đủ
          </p>
          <ul className="error" style={{ margin: 0, paddingLeft: '1.1rem' }}>
            {brief.gate.messages.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
          {brief.incomplete_preview && brief.incomplete_preview.length > 0 ? (
            <p className="muted" style={{ margin: '0.5rem 0 0', fontSize: '0.9rem' }}>
              Còn thiếu: {brief.incomplete_preview.join(' · ')}
            </p>
          ) : null}
        </div>
      ) : brief.has_context ? (
        <p style={{ margin: '0.75rem 0 0', color: 'var(--accent)' }}>
          Checklist client đạt yêu cầu cho giai đoạn Onboard.
        </p>
      ) : null}

      {checklistLink ? (
        <p style={{ margin: '0.75rem 0 0' }}>
          <Link href={checklistLink} className="nav-link">
            Mở checklist agency client →
          </Link>
        </p>
      ) : null}
    </div>
  );
}
