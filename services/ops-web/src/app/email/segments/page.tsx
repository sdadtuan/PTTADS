'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { SegmentBuilder } from '@/components/email';
import {
  computeEmailSegment,
  createEmailSegment,
  fetchEmailSegments,
  patchEmailSegment,
  staffMe,
  staffRefresh,
  type EmailSegmentComputeResult,
  type EmailSegmentRow,
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
import { useToast } from '@/lib/toast';

export default function EmailSegmentsPage() {
  const router = useRouter();
  const { push } = useToast();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [segments, setSegments] = useState<EmailSegmentRow[]>([]);
  const [clientId, setClientId] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get('client_id');
    if (q) setClientId(q);
  }, []);

  const ensureAuth = useCallback(async (): Promise<string | null> => {
    let access = getAccessToken();
    if (!access) {
      router.replace('/login');
      return null;
    }
    try {
      const me = await staffMe(access);
      setUser(me);
      updateStoredUser(me);
      if (!hasCap(me, 'crm_email_mkt', 'view') && !hasCap(me, 'crm_agency', 'view')) {
        setError('Không có quyền');
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
      setUser(await staffMe(access));
      return access;
    }
  }, [router]);

  const load = useCallback(
    async (access: string) => {
      setLoading(true);
      setError('');
      try {
        const data = await fetchEmailSegments(access, {
          client_id: clientId.trim() || undefined,
          limit: 100,
        });
        setSegments(data.items);
        setSelectedId((prev) => (prev && !data.items.some((s) => s.id === prev) ? null : prev));
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải segments thất bại');
      } finally {
        setLoading(false);
      }
    },
    [clientId],
  );

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      await load(access);
    })();
  }, [ensureAuth, load]);

  const canWrite = user
    ? hasCap(user, 'crm_email_mkt', 'write') || hasCap(user, 'crm_agency', 'create')
    : false;

  async function handleCreate(payload: {
    name: string;
    segment_type: string;
    definition_json: Record<string, unknown>;
  }): Promise<EmailSegmentRow> {
    const access = getAccessToken();
    if (!access || !clientId.trim()) throw new Error('Thiếu client UUID');
    const row = await createEmailSegment(access, {
      client_id: clientId.trim(),
      name: payload.name,
      segment_type: payload.segment_type,
      definition_json: payload.definition_json,
    });
    push(`Đã tạo segment "${row.name}"`, 'success');
    await load(access);
    return row;
  }

  async function handleSave(
    segmentId: string,
    payload: { name: string; segment_type: string; definition_json: Record<string, unknown> },
  ) {
    const access = getAccessToken();
    if (!access) return;
    await patchEmailSegment(access, segmentId, payload);
    push('Đã lưu định nghĩa segment', 'success');
    await load(access);
  }

  async function handleCompute(segmentId: string): Promise<EmailSegmentComputeResult> {
    const access = getAccessToken();
    if (!access) throw new Error('Unauthorized');
    const out = await computeEmailSegment(access, segmentId);
    push(`Compute xong: ${out.member_count.toLocaleString()} contacts`, 'success');
    await load(access);
    return out;
  }

  async function handleDuplicate(segment: EmailSegmentRow): Promise<EmailSegmentRow> {
    const access = getAccessToken();
    if (!access) throw new Error('Unauthorized');
    const row = await createEmailSegment(access, {
      client_id: segment.client_id,
      name: `${segment.name} (copy)`,
      segment_type: segment.segment_type,
      definition_json: segment.definition_json ?? {},
    });
    push(`Đã duplicate → "${row.name}"`, 'success');
    await load(access);
    return row;
  }

  if (!user) return <main style={{ padding: '2rem' }}><p className="muted">Đang tải…</p></main>;

  return (
    <main style={{ maxWidth: 1200, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={() => { clearSession(); router.push('/login'); }} />
      <div className="card" style={{ marginBottom: '1rem' }}>
        <p className="muted" style={{ marginTop: 0 }}>EM-8b E-07 — Segment builder</p>
        <Link href="/email/hub" className="btn btn-secondary btn-sm">← Hub</Link>
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <label style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            Client UUID
            <input value={clientId} onChange={(e) => setClientId(e.target.value)} placeholder="Client UUID" style={{ width: 280 }} />
          </label>
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => { const a = getAccessToken(); if (a) void load(a); }}>
            Làm mới
          </button>
        </div>
      </div>
      {error ? <p className="error">{error}</p> : null}
      {loading && segments.length === 0 ? <p className="muted">Đang tải segments…</p> : null}
      <SegmentBuilder
        segments={segments}
        selectedId={selectedId}
        clientId={clientId}
        canWrite={canWrite}
        onSelect={setSelectedId}
        onCreate={handleCreate}
        onSave={handleSave}
        onCompute={handleCompute}
        onDuplicate={handleDuplicate}
      />
    </main>
  );
}
