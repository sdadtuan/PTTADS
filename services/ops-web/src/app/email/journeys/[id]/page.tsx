'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { EmailStatusBadge, JourneyCanvasEditor } from '@/components/email';
import {
  activateEmailJourney,
  fetchEmailJourney,
  patchEmailJourney,
  staffMe,
  staffRefresh,
  type EmailJourneyRow,
} from '@/lib/api';
import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  hasCap,
  updateAccessToken,
  updateStoredUser,
  type StoredStaffUser,
} from '@/lib/auth';

type GraphNode = { id: string; type: string; config?: Record<string, unknown> };
type GraphJson = { nodes: GraphNode[]; edges: Array<{ from: string; to: string; label?: string }> };

export default function EmailJourneyDetailPage() {
  const router = useRouter();
  const params = useParams();
  const journeyId = String(params.id ?? '');
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [journey, setJourney] = useState<EmailJourneyRow | null>(null);
  const [error, setError] = useState('');
  const [activating, setActivating] = useState(false);

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
      setError('');
      try {
        setJourney(await fetchEmailJourney(access, journeyId));
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải journey thất bại');
      }
    },
    [journeyId],
  );

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      await load(access);
    })();
  }, [ensureAuth, load]);

  async function activate() {
    const access = getAccessToken();
    if (!access) return;
    setActivating(true);
    setError('');
    try {
      setJourney(await activateEmailJourney(access, journeyId));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Activate thất bại');
    } finally {
      setActivating(false);
    }
  }

  if (!user) return <main style={{ padding: '2rem' }}><p className="muted">Đang tải…</p></main>;

  const canWrite = hasCap(user, 'crm_email_mkt', 'write') || hasCap(user, 'crm_agency', 'create');
  const graph = (journey?.graph_json ?? { nodes: [], edges: [] }) as GraphJson;
  const editable = canWrite && journey && (journey.status === 'draft' || journey.status === 'paused');

  async function saveGraph(next: GraphJson) {
    const access = getAccessToken();
    if (!access) return;
    setJourney(await patchEmailJourney(access, journeyId, { graph_json: next }));
  }

  return (
    <main style={{ maxWidth: 960, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={() => { clearSession(); router.push('/login'); }} />
      <div className="card" style={{ marginBottom: '1rem' }}>
        <p className="muted" style={{ marginTop: 0 }}>EM-12 E-10b — Journey canvas editor</p>
        <Link href="/email/journeys" className="btn btn-secondary btn-sm">← Journeys</Link>
        {journey ? (
            <p className="muted">
              {journey.client_name} · <EmailStatusBadge status={journey.status} /> · enrolled {journey.enrolled_count}
            </p>
        ) : null}
      </div>
      {error ? <p className="error">{error}</p> : null}
      {journey ? (
        <>
          <div className="card" style={{ marginBottom: '1rem' }}>
            <h2 style={{ marginTop: 0 }}>{journey.name}</h2>
            <p className="muted">Entry segment: {journey.entry_segment_name ?? '—'}</p>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              {canWrite && (journey.status === 'draft' || journey.status === 'paused') ? (
                <button type="button" className="btn btn-sm" disabled={activating} onClick={() => void activate()}>
                  {activating ? '…' : 'Activate journey'}
                </button>
              ) : null}
            </div>
          </div>
          <div className="card">
            <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Canvas</h2>
            <JourneyCanvasEditor graph={graph} editable={Boolean(editable)} onSave={editable ? saveGraph : undefined} />
          </div>
        </>
      ) : null}
    </main>
  );
}
