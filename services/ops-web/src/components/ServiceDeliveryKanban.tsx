'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';
import {
  fetchServiceLifecycleAdvanceInfo,
  patchServiceLifecycle,
  type ServiceLifecycleRow,
} from '@/lib/api';

const STAGES = ['lead', 'consult', 'proposal', 'onboard', 'deliver', 'handover', 'retain'] as const;
const STAGE_LABELS: Record<string, string> = {
  lead: 'Lead',
  consult: 'Tư vấn',
  proposal: 'Báo giá',
  onboard: 'Onboard',
  deliver: 'Triển khai',
  handover: 'Bàn giao',
  retain: 'Giữ chân',
};

function nextStage(stage: string): string | null {
  const idx = STAGES.indexOf(stage as (typeof STAGES)[number]);
  if (idx < 0 || idx >= STAGES.length - 1) return null;
  return STAGES[idx + 1];
}

type Props = {
  rows: ServiceLifecycleRow[];
  funnelStats?: Record<string, number>;
  token?: string;
  canEdit?: boolean;
  onRefresh?: () => void;
  onNotify?: (msg: string, isError?: boolean) => void;
};

export function ServiceDeliveryKanban({
  rows,
  funnelStats,
  token,
  canEdit,
  onRefresh,
  onNotify,
}: Props) {
  const [dragId, setDragId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  const byStage = useMemo(() => {
    const out: Record<string, ServiceLifecycleRow[]> = {};
    for (const s of STAGES) out[s] = [];
    for (const row of rows) {
      const st = String(row.stage ?? 'lead');
      if (!out[st]) out[st] = [];
      out[st].push(row);
    }
    return out;
  }, [rows]);

  async function tryAdvance(lifecycleId: number, fromStage: string, toStage: string) {
    if (!token || !canEdit || busy) return;
    const expected = nextStage(fromStage);
    if (!expected || expected !== toStage) {
      onNotify?.('Chỉ được kéo sang cột kế tiếp (strict DnD)', true);
      return;
    }
    setBusy(true);
    try {
      const info = await fetchServiceLifecycleAdvanceInfo(token, lifecycleId);
      if (!info.can_advance_forward) {
        onNotify?.(String(info.block_reason || 'Chưa đủ điều kiện chuyển stage'), true);
        return;
      }
      await patchServiceLifecycle(token, lifecycleId, { stage: toStage });
      onNotify?.(`Đã chuyển lifecycle #${lifecycleId} → ${STAGE_LABELS[toStage] ?? toStage}`);
      onRefresh?.();
    } catch (err) {
      onNotify?.(err instanceof Error ? err.message : 'Chuyển stage thất bại', true);
    } finally {
      setBusy(false);
      setDragId(null);
    }
  }

  return (
    <div style={{ display: 'grid', gap: '1rem' }}>
      {funnelStats && Object.keys(funnelStats).length > 0 ? (
        <div className="card" style={{ padding: '0.75rem 1rem' }}>
          <strong>Funnel active</strong>
          <span className="muted" style={{ marginLeft: '0.5rem' }}>
            {STAGES.map((s) => `${STAGE_LABELS[s] ?? s}: ${funnelStats[s] ?? 0}`).join(' · ')}
          </span>
        </div>
      ) : null}
      {canEdit ? (
        <p className="muted" style={{ margin: 0, fontSize: '0.85rem' }}>
          Kéo thả card sang cột kế tiếp khi gate pass. Lùi stage: mở chi tiết workflow.
        </p>
      ) : null}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
          gap: '0.65rem',
          alignItems: 'start',
        }}
      >
        {STAGES.map((stage) => {
          const prevStage = STAGES[STAGES.indexOf(stage) - 1];
          const isNextCol = dragId != null && prevStage && rows.find((r) => r.id === dragId)?.stage === prevStage;
          return (
            <div
              key={stage}
              onDragOver={(e) => {
                if (isNextCol) e.preventDefault();
              }}
              onDrop={(e) => {
                e.preventDefault();
                const id = Number(e.dataTransfer.getData('lifecycleId'));
                const from = e.dataTransfer.getData('fromStage');
                if (id > 0 && from) void tryAdvance(id, from, stage);
              }}
              style={{
                background: isNextCol ? 'rgba(34, 197, 94, 0.08)' : 'var(--bg)',
                border: `1px solid ${isNextCol ? 'var(--accent, #16a34a)' : 'var(--border)'}`,
                borderRadius: 10,
                minHeight: 120,
                padding: '0.5rem',
                transition: 'border-color 0.15s',
              }}
            >
              <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.4rem' }}>
                {STAGE_LABELS[stage] ?? stage}
                <span className="muted" style={{ marginLeft: 4 }}>
                  ({byStage[stage]?.length ?? 0})
                </span>
              </div>
              <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'grid', gap: '0.35rem' }}>
                {(byStage[stage] ?? []).map((lc) => (
                  <li
                    key={lc.id}
                    draggable={Boolean(canEdit && token && nextStage(String(lc.stage ?? '')))}
                    onDragStart={(e) => {
                      setDragId(lc.id);
                      e.dataTransfer.setData('lifecycleId', String(lc.id));
                      e.dataTransfer.setData('fromStage', String(lc.stage ?? 'lead'));
                    }}
                    onDragEnd={() => setDragId(null)}
                    style={{ cursor: canEdit ? 'grab' : 'default' }}
                  >
                    <Link
                      href={`/crm/service-delivery/${lc.id}`}
                      className="nav-link"
                      style={{
                        display: 'block',
                        padding: '0.35rem 0.45rem',
                        borderRadius: 6,
                        border: '1px solid var(--border)',
                        fontSize: '0.82rem',
                        background: dragId === lc.id ? 'var(--bg-subtle)' : undefined,
                      }}
                      onClick={(e) => {
                        if (dragId != null) e.preventDefault();
                      }}
                    >
                      #{lc.id} · {lc.service_slug}
                      {lc.customer_id ? ` · KH #${lc.customer_id}` : ''}
                      {lc.assigned_am ? ` · AM #${lc.assigned_am}` : ''}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </div>
  );
}
