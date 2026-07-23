'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  fetchServiceLifecycleMarketingPlan,
  patchServiceLifecycleMarketingPlan,
} from '@/lib/api';
import { hasCap, type StoredStaffUser } from '@/lib/auth';

const STRATEGY_LABELS: Record<string, string> = {
  target_market: 'Thị trường mục tiêu (tóm tắt)',
  market_message: 'Thông điệp thị trường',
  media_reach: 'Kênh tiếp cận / Media',
  conversion_strategy: 'Chiến lược chuyển đổi',
  retention_system: 'Hệ thống giữ chân',
  nurture_system: 'Nuôi dưỡng lead',
  world_class_experience: 'Trải nghiệm đẳng cấp',
  lifecycle_extension: 'Gia hạn lifecycle',
  referral_engine: 'Giới thiệu / Referral',
};

const TMMT_PROF_LABELS: Record<string, string> = {
  market_context: 'Bối cảnh thị trường',
  tam_sam_som: 'TAM / SAM / SOM',
  geo_behavior: 'Địa lý & hành vi',
  segmentation_icp: 'Phân khúc & ICP',
  personas_roles: 'Persona & vai trò mua',
  jobs_to_be_done: 'Jobs-to-be-done',
  pains_desired_outcomes: 'Pain & kết quả mong muốn',
  buy_triggers_obstacles: 'Trigger mua & rào cản',
  criteria_vs_alternatives: 'Tiêu chí vs phương án thay thế',
  insights_evidence: 'Insight & bằng chứng',
  segment_priorities: 'Ưu tiên phân khúc',
  success_hypotheses_next: 'Giả thuyết & bước tiếp theo',
};

type MarketingPlanPayload = {
  plan: {
    id?: number;
    name?: string;
    north_star?: string;
    objectives?: string;
    strategy_framework?: Record<string, string>;
    target_market_prof?: Record<string, string>;
  } | null;
  validation: { ok: boolean; messages: string[] };
  tmmt_core_keys?: string[];
  tmmt_prof_keys?: string[];
  tmmt_min_filled?: number;
  filled_count?: number;
};

interface Props {
  token: string;
  user: StoredStaffUser;
  lifecycleId: number;
  stage: string;
  onSaved?: () => void;
}

export function LifecycleTmmtPanel({ token, user, lifecycleId, stage, onSaved }: Props) {
  const [data, setData] = useState<MarketingPlanPayload | null>(null);
  const [draftSf, setDraftSf] = useState<Record<string, string>>({});
  const [draftProf, setDraftProf] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const canEdit = hasCap(user, 'crm_board', 'edit');

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const out = await fetchServiceLifecycleMarketingPlan(token, lifecycleId);
      setData(out as MarketingPlanPayload);
      const plan = (out as MarketingPlanPayload).plan;
      setDraftSf(plan?.strategy_framework ?? {});
      setDraftProf(plan?.target_market_prof ?? {});
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tải TMMT thất bại');
    } finally {
      setLoading(false);
    }
  }, [token, lifecycleId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function save() {
    if (!canEdit) return;
    setSaving(true);
    setMessage('');
    setError('');
    try {
      const out = await patchServiceLifecycleMarketingPlan(token, lifecycleId, {
        target_market_prof: draftProf,
        strategy_framework: draftSf,
      });
      setData(out as MarketingPlanPayload);
      setMessage('Đã lưu TMMT chính thức');
      onSaved?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lưu TMMT thất bại');
    } finally {
      setSaving(false);
    }
  }

  const validation = data?.validation ?? { ok: false, messages: [] };
  const filled = data?.filled_count ?? 0;
  const minFilled = data?.tmmt_min_filled ?? 6;
  const totalProf = data?.tmmt_prof_keys?.length ?? 12;
  const coreKeys = new Set(data?.tmmt_core_keys ?? []);

  return (
    <div className="card" style={{ padding: '1rem', display: 'grid', gap: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.75rem', flexWrap: 'wrap' }}>
        <div>
          <h3 style={{ margin: 0, fontSize: '1rem' }}>TMMT chính thức (R5)</h3>
          <p className="muted" style={{ margin: '0.35rem 0 0' }}>
            Tiến độ chi tiết: {filled}/{totalProf} · tối thiểu {minFilled} mục · 4 trường core bắt buộc
          </p>
        </div>
        {validation.ok ? (
          <span style={{ color: 'var(--accent)', fontWeight: 600 }}>Gate ✓ — có thể chuyển Deliver</span>
        ) : (
          <span className="error" style={{ fontWeight: 600 }}>Gate chưa pass</span>
        )}
      </div>

      {loading ? <p className="muted">Đang tải…</p> : null}
      {error ? <p className="error">{error}</p> : null}
      {message ? <p style={{ color: 'var(--accent)' }}>{message}</p> : null}

      {!validation.ok ? (
        <ul className="error" style={{ margin: 0, paddingLeft: '1.1rem' }}>
          {validation.messages.map((m) => (
            <li key={m}>{m}</li>
          ))}
        </ul>
      ) : null}

      {stage === 'onboard' && !validation.ok ? (
        <p className="muted" style={{ margin: 0, fontSize: '0.9rem' }}>
          Hoàn thiện TMMT trước khi bấm <strong>Chuyển → Triển khai</strong> trên tab Workflow.
        </p>
      ) : null}

      {!data?.plan ? (
        <p className="error">Chưa có kế hoạch MKT chính thức — kiểm tra promote từ presales.</p>
      ) : (
        <>
          <section>
            <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.95rem' }}>Khung chiến lược</h4>
            <div style={{ display: 'grid', gap: '0.65rem' }}>
              {Object.entries(STRATEGY_LABELS).map(([key, label]) => (
                <label key={key} style={{ display: 'grid', gap: '0.3rem' }}>
                  <span className="muted">{label}</span>
                  <textarea
                    rows={key === 'target_market' ? 2 : 2}
                    value={draftSf[key] ?? ''}
                    disabled={!canEdit || saving}
                    onChange={(e) => setDraftSf((prev) => ({ ...prev, [key]: e.target.value }))}
                    style={{
                      background: 'var(--bg)',
                      border: '1px solid var(--border)',
                      borderRadius: 8,
                      padding: '0.55rem 0.75rem',
                      color: 'var(--text)',
                    }}
                  />
                </label>
              ))}
            </div>
          </section>

          <section>
            <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.95rem' }}>Thuyết minh thị trường mục tiêu</h4>
            <div style={{ display: 'grid', gap: '0.65rem' }}>
              {(data.tmmt_prof_keys ?? Object.keys(TMMT_PROF_LABELS)).map((key) => (
                <label key={key} style={{ display: 'grid', gap: '0.3rem' }}>
                  <span className="muted">
                    {TMMT_PROF_LABELS[key] ?? key}
                    {coreKeys.has(key) ? ' *' : ''}
                  </span>
                  <textarea
                    rows={2}
                    value={draftProf[key] ?? ''}
                    disabled={!canEdit || saving}
                    onChange={(e) => setDraftProf((prev) => ({ ...prev, [key]: e.target.value }))}
                    style={{
                      background: 'var(--bg)',
                      border: coreKeys.has(key) && !String(draftProf[key] ?? '').trim() ? '1px solid var(--accent)' : '1px solid var(--border)',
                      borderRadius: 8,
                      padding: '0.55rem 0.75rem',
                      color: 'var(--text)',
                    }}
                  />
                </label>
              ))}
            </div>
          </section>

          {canEdit ? (
            <button type="button" className="btn btn-sm" disabled={saving} onClick={() => void save()}>
              Lưu TMMT
            </button>
          ) : null}
        </>
      )}
    </div>
  );
}
