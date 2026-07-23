import { ReviewQueuePublicState } from './leads-funnel.types';
import {
  CONTACT_OK_CARE_STATUS,
  parseLeadMeta,
  parseStagesDoneJson,
  presalesCareGateState,
} from './care-pipeline.util';

export const REVIEW_QUEUE_REASON = 'b2_no_contact_ok';
export const DEFAULT_B2_CONTACT_DEADLINE_HOURS = 24;

export function normalizeB2ContactDeadlineHours(raw: unknown): number {
  const n = Number(raw);
  const hours = Number.isFinite(n) ? Math.trunc(n) : DEFAULT_B2_CONTACT_DEADLINE_HOURS;
  return Math.max(1, Math.min(hours, 168));
}

export function reviewQueueFromMeta(meta: Record<string, unknown> | null | undefined): Record<string, unknown> {
  const rq = meta?.review_queue;
  return rq && typeof rq === 'object' && !Array.isArray(rq) ? (rq as Record<string, unknown>) : {};
}

export function isLeadInReviewQueue(meta: Record<string, unknown> | null | undefined): boolean {
  return Boolean(reviewQueueFromMeta(meta).active);
}

export function parseTs(raw: string | null | undefined): Date | null {
  const s = String(raw || '').trim();
  if (!s) return null;
  const normalized = s.slice(0, 19).replace('T', ' ');
  const iso = normalized.includes(' ') ? normalized.replace(' ', 'T') + 'Z' : normalized;
  const d = new Date(iso);
  if (!Number.isNaN(d.getTime())) return d;
  const d2 = new Date(s);
  return Number.isNaN(d2.getTime()) ? null : d2;
}

export function reviewQueuePublicState(
  meta: Record<string, unknown> | null | undefined,
  assignedAt = '',
  now = new Date(),
): ReviewQueuePublicState {
  const rq = reviewQueueFromMeta(meta);
  if (!rq.active) return { active: false };
  const queuedAt = String(rq.queued_at || '');
  const assignedSnap = String(rq.assigned_at || assignedAt || '');
  const deadlineHours = normalizeB2ContactDeadlineHours(rq.deadline_hours);
  let hoursWaiting: number | null = null;
  const assignedDt = parseTs(assignedSnap);
  if (assignedDt) {
    hoursWaiting = Math.round(((now.getTime() - assignedDt.getTime()) / 3600000) * 10) / 10;
  }
  const prev = rq.previous_owner_id;
  return {
    active: true,
    reason: String(rq.reason || REVIEW_QUEUE_REASON),
    queued_at: queuedAt,
    assigned_at: assignedSnap,
    deadline_hours: deadlineHours,
    previous_owner_id:
      prev === null || prev === undefined || prev === '' || prev === 0 ? null : Number(prev),
    hours_waiting: hoursWaiting,
    message: `Quá ${deadlineHours}h kể từ phân công — chưa có báo cáo 「Liên hệ OK» (${CONTACT_OK_CARE_STATUS}).`,
  };
}

export function leadB2OverdueForReview(
  row: {
    owner_id: number | null;
    status: string;
    is_duplicate: number;
    meta_json: string;
    care_stages_done_json: string;
    first_assigned_at?: string;
    updated_at?: string;
  },
  deadlineHours: number,
  now = new Date(),
): boolean {
  if (!row.owner_id) return false;
  const st = String(row.status || '').trim().toLowerCase();
  if (st === 'lost' || row.is_duplicate) return false;
  const meta = parseLeadMeta(row.meta_json);
  if (isLeadInReviewQueue(meta)) return false;
  const gate = presalesCareGateState('', row.care_stages_done_json);
  if (gate.complete) return false;
  const assignedAt = row.first_assigned_at || row.updated_at || '';
  const assignedDt = parseTs(assignedAt);
  if (!assignedDt) return false;
  const elapsedH = (now.getTime() - assignedDt.getTime()) / 3600000;
  return elapsedH >= deadlineHours;
}
