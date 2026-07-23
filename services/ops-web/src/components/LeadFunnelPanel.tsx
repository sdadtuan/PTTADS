'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  advanceLeadPresales,
  completeLeadCareStage,
  ensureLeadPresales,
  fetchLeadFunnel,
  fetchLeadPresalesConsultGate,
  fetchLeadPresalesMarketingPlan,
  patchLeadPresalesMarketingPlan,
  patchLeadPresalesTask,
  releaseLeadReviewQueue,
  submitLeadCareReport,
  type LeadFunnelSnapshot,
} from '@/lib/api';
import { hasCap, type StoredStaffUser } from '@/lib/auth';

const STRATEGY_LABELS: Record<string, string> = {
  target_market: 'Thị trường mục tiêu',
  market_message: 'Thông điệp thị trường',
  media_reach: 'Kênh tiếp cận / Media',
  conversion_strategy: 'Chiến lược chuyển đổi',
  retention_system: 'Hệ thống giữ chân',
  nurture_system: 'Nuôi dưỡng lead',
  world_class_experience: 'Trải nghiệm đẳng cấp',
  lifecycle_extension: 'Gia hạn lifecycle',
  referral_engine: 'Giới thiệu / Referral',
};

interface ConsultGateState {
  ok: boolean;
  level: string;
  messages: string[];
  requires_confirm: boolean;
  requires_override: boolean;
  bant_total?: number;
  decision?: string;
}

const FUNNEL_STEPS = [
  { key: 'b2', label: 'B2 Liên hệ' },
  { key: 'lead', label: 'Pre-sales Lead' },
  { key: 'consult', label: 'Tư vấn' },
  { key: 'proposal', label: 'Báo giá' },
] as const;

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
  const [planName, setPlanName] = useState('');
  const [planNorthStar, setPlanNorthStar] = useState('');
  const [planObjectives, setPlanObjectives] = useState('');
  const [planStrategy, setPlanStrategy] = useState<Record<string, string>>({});
  const [planValidation, setPlanValidation] = useState<string[]>([]);
  const [consultGate, setConsultGate] = useState<ConsultGateState | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const snap = await fetchLeadFunnel(token, leadId);
      setFunnel(snap);
      if (snap.presales) {
        if (snap.presales.presales.stage === 'lead') {
          try {
            const cg = await fetchLeadPresalesConsultGate(token, leadId);
            setConsultGate(cg.gate);
          } catch {
            setConsultGate(null);
          }
        } else {
          setConsultGate(null);
        }
        if (snap.presales.presales.stage === 'proposal') {
          try {
            const mp = await fetchLeadPresalesMarketingPlan(token, leadId);
            setPlanName(String(mp.plan.name ?? ''));
            setPlanNorthStar(String(mp.plan.north_star ?? ''));
            setPlanObjectives(String(mp.plan.objectives ?? ''));
            let sf: Record<string, string> = {};
            try {
              sf = JSON.parse(String(mp.plan.strategy_framework_json ?? '{}')) as Record<string, string>;
            } catch {
              sf = {};
            }
            setPlanStrategy(sf);
            setPlanValidation(mp.validation.messages ?? []);
          } catch {
            setPlanValidation([]);
          }
        }
      }
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

  function activeStepKey(): string {
    if (!funnel) return 'b2';
    if (!funnel.care_pipeline.all_complete) return 'b2';
    if (!funnel.presales) return 'lead';
    return funnel.presales.presales.stage;
  }

  if (loading && !funnel) {
    return <p className="muted">Đang tải funnel B2 / pre-sales…</p>;
  }
  if (!funnel) return null;

  const b2Stage = funnel.care_pipeline.stages[0];
  const inReview = funnel.review_queue.active;
  const activeStep = activeStepKey();

  return (
    <section className="card stack-gap" style={{ marginTop: '1rem' }}>
      <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Funnel B2 → Pre-sales</h2>

      <div className="funnel-stepper" style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
        {FUNNEL_STEPS.map((step, idx) => {
          const presalesIdx = funnel.presales
            ? FUNNEL_STEPS.findIndex((s) => s.key === funnel.presales!.presales.stage)
            : -1;
          const done =
            step.key === 'b2'
              ? funnel.care_pipeline.all_complete
              : presalesIdx >= idx;
          const current = step.key === activeStep;
          return (
            <span
              key={step.key}
              className={`badge${current ? ' badge-active' : ''}`}
              style={{
                padding: '0.25rem 0.5rem',
                borderRadius: 999,
                fontSize: '0.8rem',
                background: current ? '#1d4ed8' : done ? '#dcfce7' : '#f3f4f6',
                color: current ? '#fff' : done ? '#166534' : '#374151',
              }}
            >
              {step.label}
            </span>
          );
        })}
      </div>

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
              {consultGate && funnel.presales.presales.stage === 'lead' && (
                <div
                  className="banner"
                  style={{
                    marginBottom: '0.75rem',
                    background: consultGate.ok ? '#ecfdf5' : '#fef2f2',
                    border: `1px solid ${consultGate.ok ? '#86efac' : '#fecaca'}`,
                  }}
                >
                  <strong>Gate chuyển Tư vấn (Intake)</strong>
                  <ul style={{ margin: '0.35rem 0 0', paddingLeft: '1.1rem', fontSize: '0.9rem' }}>
                    {consultGate.messages.map((m) => (
                      <li key={m}>{m}</li>
                    ))}
                  </ul>
                  {consultGate.bant_total != null && (
                    <p className="muted" style={{ margin: '0.35rem 0 0', fontSize: '0.85rem' }}>
                      BANT {consultGate.bant_total}/30 · decision: {consultGate.decision || '—'}
                    </p>
                  )}
                </div>
              )}
              {canEdit && (
                <button
                  type="button"
                  className="btn btn-sm"
                  disabled={busy}
                  title={funnel.presales.advance.block_reason}
                  onClick={() =>
                    void run(async () => {
                      const reason = funnel.presales?.advance.block_reason ?? '';
                      const needsConfirm =
                        !funnel.presales?.advance.can_advance_forward &&
                        (reason.includes('Nurture') ||
                          reason.includes('BANT') ||
                          reason.includes('cân nhắc'));
                      if (
                        !funnel.presales?.advance.can_advance_forward &&
                        !needsConfirm &&
                        !window.confirm(reason || 'Không thể chuyển giai đoạn')
                      ) {
                        return;
                      }
                      if (needsConfirm && !window.confirm(reason || 'Xác nhận chuyển giai đoạn?')) {
                        return;
                      }
                      const out = await advanceLeadPresales(token, leadId, { confirm: true });
                      setFunnel(out.funnel);
                      onMessage?.('Đã chuyển giai đoạn pre-sales');
                      await reload();
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

              {funnel.presales.presales.stage === 'proposal' && (
                <div className="stack-gap" style={{ marginTop: '1rem' }}>
                  <h4 style={{ margin: 0 }}>KH Marketing sơ bộ @ Proposal</h4>
                  {planValidation.length > 0 && (
                    <ul className="muted" style={{ fontSize: '0.85rem', margin: 0, paddingLeft: '1.1rem' }}>
                      {planValidation.map((m) => (
                        <li key={m}>{m}</li>
                      ))}
                    </ul>
                  )}
                  <label>
                    Tên kế hoạch
                    <input
                      type="text"
                      value={planName}
                      disabled={!canEdit || busy}
                      onChange={(e) => setPlanName(e.target.value)}
                      style={{ width: '100%', marginTop: '0.25rem' }}
                    />
                  </label>
                  <label>
                    North Star
                    <input
                      type="text"
                      value={planNorthStar}
                      disabled={!canEdit || busy}
                      onChange={(e) => setPlanNorthStar(e.target.value)}
                      style={{ width: '100%', marginTop: '0.25rem' }}
                    />
                  </label>
                  <label>
                    Mục tiêu chiến lược
                    <textarea
                      rows={2}
                      value={planObjectives}
                      disabled={!canEdit || busy}
                      onChange={(e) => setPlanObjectives(e.target.value)}
                      style={{ width: '100%', marginTop: '0.25rem' }}
                    />
                  </label>
                  {Object.entries(STRATEGY_LABELS).map(([key, label]) => (
                    <label key={key}>
                      {label}
                      <textarea
                        rows={2}
                        value={planStrategy[key] ?? ''}
                        disabled={!canEdit || busy}
                        onChange={(e) =>
                          setPlanStrategy((prev) => ({ ...prev, [key]: e.target.value }))
                        }
                        style={{ width: '100%', marginTop: '0.25rem' }}
                      />
                    </label>
                  ))}
                  {canEdit && (
                    <button
                      type="button"
                      className="btn btn-sm"
                      disabled={busy}
                      onClick={() =>
                        void run(async () => {
                          const out = await patchLeadPresalesMarketingPlan(token, leadId, {
                            name: planName,
                            north_star: planNorthStar,
                            objectives: planObjectives,
                            strategy_framework: planStrategy,
                          });
                          setFunnel(out.funnel);
                          setPlanValidation(out.validation.messages ?? []);
                          onMessage?.('Đã lưu KH MKT sơ bộ');
                        })
                      }
                    >
                      Lưu KH MKT sơ bộ
                    </button>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </section>
  );
}
