'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  advanceLeadPresales,
  completeLeadCareStage,
  ensureLeadPresales,
  fetchLeadFunnel,
  patchLeadPresalesTask,
  releaseLeadReviewQueue,
  submitLeadCareReport,
  type LeadFunnelSnapshot,
} from '@/lib/api';
import { hasCap, type StoredStaffUser } from '@/lib/auth';

interface Props {
  token: string;
  leadId: number;
  user: StoredStaffUser | null;
  serviceSlug?: string;
  onMessage?: (msg: string) => void;
  onError?: (msg: string) => void;
}

export function LeadFunnelPanel({ token, leadId, user, serviceSlug, onMessage, onError }: Props) {
  const [funnel, setFunnel] = useState<LeadFunnelSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [careNote, setCareNote] = useState('');
  const [careReport, setCareReport] = useState('Đã liên hệ KH — xác nhận nhu cầu');
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const snap = await fetchLeadFunnel(token, leadId);
      setFunnel(snap);
    } catch (err) {
      onError?.(err instanceof Error ? err.message : 'Tải funnel thất bại');
    } finally {
      setLoading(false);
    }
  }, [token, leadId, onError]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const canEdit = Boolean(user && hasCap(user, 'crm_leads', 'edit'));
  const canAssign = Boolean(user && hasCap(user, 'crm_leads', 'assign'));

  async function run(action: () => Promise<void>) {
    setBusy(true);
    try {
      await action();
    } catch (err) {
      onError?.(err instanceof Error ? err.message : 'Thao tác thất bại');
    } finally {
      setBusy(false);
    }
  }

  if (loading && !funnel) {
    return <p className="muted">Đang tải funnel B2 / pre-sales…</p>;
  }
  if (!funnel) return null;

  const b2Stage = funnel.care_pipeline.stages[0];
  const inReview = funnel.review_queue.active;

  return (
    <section className="card stack-gap" style={{ marginTop: '1rem' }}>
      <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Funnel B2 → Pre-sales</h2>

      {inReview && (
        <div className="banner banner-warn">
          <strong>Phải tra soát (GDKD)</strong>
          <p style={{ margin: '0.35rem 0 0' }}>{funnel.review_queue.message}</p>
          {canAssign && (
            <button
              type="button"
              className="btn btn-sm"
              disabled={busy}
              style={{ marginTop: '0.5rem' }}
              onClick={() =>
                void run(async () => {
                  await releaseLeadReviewQueue(token, leadId, { mode: 'auto', note: 'Release từ ops-web' });
                  onMessage?.('Đã release lead khỏi review queue');
                  await reload();
                })
              }
            >
              Release (auto gán lại AM)
            </button>
          )}
        </div>
      )}

      <div className="card-inner">
        <h3 style={{ marginTop: 0 }}>B2 — {b2Stage?.label ?? 'Liên hệ lần đầu'}</h3>
        <p className="muted" style={{ fontSize: '0.9rem' }}>{b2Stage?.hint}</p>
        <p>
          Gate pre-sales:{' '}
          <strong>{funnel.presales_care_gate.complete ? '✓ Mở' : '🔒 Chưa hoàn thành B2'}</strong>
        </p>
        {!funnel.care_pipeline.all_complete && canEdit && !inReview && (
          <div className="stack-gap" style={{ marginTop: '0.75rem' }}>
            <label>
              Báo cáo chăm sóc (Liên hệ OK)
              <textarea
                rows={2}
                value={careReport}
                onChange={(e) => setCareReport(e.target.value)}
                style={{ width: '100%', marginTop: '0.25rem' }}
              />
            </label>
            <button
              type="button"
              className="btn btn-sm"
              disabled={busy}
              onClick={() =>
                void run(async () => {
                  await submitLeadCareReport(token, leadId, { content: careReport });
                  onMessage?.('Đã gửi báo cáo Liên hệ OK');
                  await reload();
                })
              }
            >
              Gửi báo cáo Liên hệ OK
            </button>
            <label>
              Ghi chú hoàn thành B2 (≥ 3 ký tự)
              <input
                type="text"
                value={careNote}
                onChange={(e) => setCareNote(e.target.value)}
                style={{ width: '100%', marginTop: '0.25rem' }}
              />
            </label>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              disabled={busy || careNote.trim().length < 3}
              onClick={() =>
                void run(async () => {
                  const out = await completeLeadCareStage(token, leadId, careNote.trim());
                  setFunnel(out.funnel);
                  setCareNote('');
                  onMessage?.('Đã hoàn thành B2');
                })
              }
            >
              Hoàn thành B2
            </button>
          </div>
        )}
        {funnel.care_pipeline.all_complete && (
          <p style={{ color: '#15803d', marginBottom: 0 }}>✓ B2 đã hoàn thành</p>
        )}
      </div>

      {funnel.presales_on_lead_enabled && funnel.presales_care_gate.complete && !inReview && (
        <div className="card-inner">
          <h3 style={{ marginTop: 0 }}>Pre-sales</h3>
          {!funnel.presales && canEdit && (
            <button
              type="button"
              className="btn btn-primary btn-sm"
              disabled={busy || !serviceSlug}
              onClick={() =>
                void run(async () => {
                  const slug = serviceSlug || 'dich-vu-seo-tong-the';
                  const out = await ensureLeadPresales(token, leadId, slug);
                  setFunnel(out.funnel);
                  onMessage?.('Đã bắt đầu pre-sales');
                })
              }
            >
              Bắt đầu pre-sales{serviceSlug ? ` (${serviceSlug})` : ''}
            </button>
          )}
          {funnel.presales && (
            <>
              <p>
                Giai đoạn: <strong>{funnel.presales.presales.stage}</strong> · Dịch vụ:{' '}
                {funnel.presales.presales.service_slug || '—'}
              </p>
              {(funnel.presales.tasks[funnel.presales.presales.stage] ?? []).map((task) => (
                <label key={task.id} style={{ display: 'block', marginBottom: '0.35rem' }}>
                  <input
                    type="checkbox"
                    checked={task.is_done}
                    disabled={busy || !canEdit}
                    onChange={(e) =>
                      void run(async () => {
                        const out = await patchLeadPresalesTask(token, leadId, task.id, {
                          is_done: e.target.checked,
                        });
                        setFunnel(out.funnel);
                      })
                    }
                  />{' '}
                  {task.title}
                </label>
              ))}
              {canEdit && (
                <button
                  type="button"
                  className="btn btn-sm"
                  disabled={busy || !funnel.presales.advance.can_advance_forward}
                  title={funnel.presales.advance.block_reason}
                  onClick={() =>
                    void run(async () => {
                      const out = await advanceLeadPresales(token, leadId);
                      setFunnel(out.funnel);
                      onMessage?.('Đã chuyển giai đoạn pre-sales');
                    })
                  }
                >
                  Chuyển → {funnel.presales.advance.next_stage ?? '—'}
                </button>
              )}
              {!funnel.presales.advance.can_advance_forward && funnel.presales.advance.block_reason && (
                <p className="muted" style={{ fontSize: '0.85rem' }}>
                  {funnel.presales.advance.block_reason}
                </p>
              )}
            </>
          )}
        </div>
      )}
    </section>
  );
}
