/** CRM-UC-001 / CRM-UC-008 — first call SLA for status Mới (15 minutes). */

export const CSKH_FIRST_CALL_SLA_MINUTES = 15;

export type CskhSlaState = 'ok' | 'warning' | 'breach' | 'na';

export interface CskhSlaInput {
  status: string | null | undefined;
  receivedAt: string | Date | null | undefined;
  createdAt: string | Date | null | undefined;
  firstCallAt: string | Date | null | undefined;
  now?: Date;
}

const NEW_STATUSES = new Set(['new', 'moi', 'mới']);

export function isNewLeadStatus(status: string | null | undefined): boolean {
  const raw = String(status ?? '')
    .trim()
    .toLowerCase();
  return NEW_STATUSES.has(raw);
}

function parseTs(value: string | Date | null | undefined): Date | null {
  if (value == null || value === '') return null;
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
  const d = new Date(String(value));
  return Number.isNaN(d.getTime()) ? null : d;
}

export function computeFirstCallSla(input: CskhSlaInput): {
  sla_state: CskhSlaState;
  sla_minutes_elapsed: number | null;
  sla_deadline_at: string | null;
} {
  if (!isNewLeadStatus(input.status)) {
    return { sla_state: 'na', sla_minutes_elapsed: null, sla_deadline_at: null };
  }

  const anchor = parseTs(input.receivedAt) ?? parseTs(input.createdAt);
  if (!anchor) {
    return { sla_state: 'na', sla_minutes_elapsed: null, sla_deadline_at: null };
  }

  const deadline = new Date(anchor.getTime() + CSKH_FIRST_CALL_SLA_MINUTES * 60_000);
  const firstCall = parseTs(input.firstCallAt);
  const now = input.now ?? new Date();

  if (firstCall && firstCall.getTime() <= deadline.getTime()) {
    return {
      sla_state: 'ok',
      sla_minutes_elapsed: Math.round((firstCall.getTime() - anchor.getTime()) / 60_000),
      sla_deadline_at: deadline.toISOString(),
    };
  }

  if (firstCall && firstCall.getTime() > deadline.getTime()) {
    return {
      sla_state: 'breach',
      sla_minutes_elapsed: Math.round((firstCall.getTime() - anchor.getTime()) / 60_000),
      sla_deadline_at: deadline.toISOString(),
    };
  }

  const elapsedMin = Math.round((now.getTime() - anchor.getTime()) / 60_000);
  if (now.getTime() > deadline.getTime()) {
    return {
      sla_state: 'breach',
      sla_minutes_elapsed: elapsedMin,
      sla_deadline_at: deadline.toISOString(),
    };
  }

  if (elapsedMin >= CSKH_FIRST_CALL_SLA_MINUTES - 5) {
    return {
      sla_state: 'warning',
      sla_minutes_elapsed: elapsedMin,
      sla_deadline_at: deadline.toISOString(),
    };
  }

  return {
    sla_state: 'ok',
    sla_minutes_elapsed: elapsedMin,
    sla_deadline_at: deadline.toISOString(),
  };
}

export function slaMatchesFilter(
  slaState: CskhSlaState,
  filter: 'all' | 'breach' | 'warning' | 'open',
): boolean {
  if (filter === 'all') return true;
  if (filter === 'breach') return slaState === 'breach';
  if (filter === 'warning') return slaState === 'warning' || slaState === 'breach';
  if (filter === 'open') return slaState === 'ok' || slaState === 'warning';
  return true;
}
