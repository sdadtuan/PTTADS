import { GO_THRESHOLDS } from '../intake/intake-definitions.util';
import type { IntakeSessionRow } from '../intake/intake.types';
import { SERVICE_LABELS } from '../leads-contract/lifecycle-workflow-steps.util';
import type { SvcTaskRow } from './lifecycle-tasks.repository';
import { getCrmFieldMap, SEO_SLUGS } from './lifecycle-consult-field-map.util';

export const DECISION_LABELS: Record<string, string> = {
  go: 'GO',
  nurture: 'Nurture',
  no_go: 'No-Go',
  '': '—',
};

export const TEMPERATURE_LABELS: Record<string, string> = {
  hot: 'Hot',
  warm: 'Warm',
  cold: 'Cold',
  '': '—',
};

export interface IntakeSessionBriefRow {
  id: number;
  mode: string;
  status: string;
  bant_total: number;
  decision: string;
  decision_reason: string;
  ai_summary: string;
  next_meeting_at: string;
  proposal_date: string;
  completed_at: string;
  lead_temperature: string;
}

function fieldEmpty(value: unknown): boolean {
  if (value == null) return true;
  if (typeof value === 'string') return !value.trim();
  return false;
}

function latestCompleted(sessions: IntakeSessionRow[]): IntakeSessionRow | null {
  const completed = sessions.filter((s) => s.status === 'completed');
  if (completed.length === 0) return null;
  return completed.reduce((best, s) => {
    const bestKey = `${best.completed_at ?? ''}\0${best.id}`;
    const sKey = `${s.completed_at ?? ''}\0${s.id}`;
    return sKey > bestKey ? s : best;
  });
}

function hasCompletedMode(sessions: IntakeSessionBriefRow[], mode: string): boolean {
  return sessions.some((s) => s.status === 'completed' && s.mode === mode);
}

export function consultGateLevel(decision: string, bantTotal: number): 'ok' | 'warn' | 'block' {
  if (decision === 'no_go') return 'block';
  if (decision === 'nurture') return 'warn';
  if (decision === 'go') {
    if (bantTotal >= GO_THRESHOLDS.go) return 'ok';
    return 'warn';
  }
  return 'warn';
}

function extractRedFlags(session: IntakeSessionRow | null): string[] {
  if (!session) return [];
  const answers = session.answers_json ?? {};
  const flags = answers.red_flags;
  if (!Array.isArray(flags)) return [];
  return flags.map((x) => String(x).trim()).filter(Boolean);
}

function buildHighlights(
  leadTask: { form_data: Record<string, unknown> } | null,
  latest: IntakeSessionRow | null,
): Record<string, unknown> {
  const form = leadTask?.form_data ?? {};
  let pain = String(form.need ?? '').trim();
  if (!pain && latest) {
    const answers = latest.answers_json ?? {};
    const meta = answers.meta;
    if (meta && typeof meta === 'object') {
      pain = String((meta as Record<string, unknown>).pain_summary ?? '').trim();
    }
  }
  let budgetVnd: number | null = null;
  const budget = form.budget;
  if (budget != null && budget !== '') {
    const n = Number(budget);
    budgetVnd = Number.isFinite(n) ? n : null;
  }
  return {
    pain,
    budget_vnd: budgetVnd,
    domain: String(form.domain ?? '').trim(),
    niche: String(form.niche ?? form.industry ?? '').trim(),
    goal: String(form.goal ?? form.campaign_goal ?? '').trim(),
  };
}

function buildLatestIntakeSummary(latest: IntakeSessionRow | null): string {
  if (!latest) return '';
  if (String(latest.ai_summary ?? '').trim()) {
    return String(latest.ai_summary).slice(0, 4000);
  }
  const parts = [
    latest.decision ? `Decision: ${latest.decision}` : '',
    latest.bant_total ? `BANT: ${latest.bant_total}/30` : '',
    latest.decision_reason ? String(latest.decision_reason).slice(0, 500) : '',
  ].filter(Boolean);
  return parts.join(' · ').slice(0, 4000);
}

function buildRecommendedActions(brief: Record<string, unknown>): string[] {
  const actions: string[] = [];
  const readiness = (brief.readiness ?? {}) as Record<string, unknown>;
  const serviceSlug = String(brief.service_slug ?? '');

  if (!readiness.has_any_intake) {
    actions.push('Hoàn thành Lead Intake (gọi PHẦN A) trước khi audit Consult');
    return actions;
  }
  if (!readiness.lead_task_done) {
    actions.push('Hoàn thành task Lead (tick ✓) trước khi audit Consult sâu');
  }
  const decision = String(readiness.decision ?? '');
  if (decision === 'no_go') {
    actions.push('Intake No-Go — không nên audit Consult sâu; cân nhắc đóng lifecycle');
    return actions.slice(0, 6);
  }
  if (decision === 'nurture') {
    actions.push('Nurture — cân nhắc nurture thêm trước Consult sâu');
  }
  if (!readiness.has_intake_in_person) {
    actions.push('Hẹn gặp PHẦN B (in_person) trước audit Consult sâu');
  }
  if (SEO_SLUGS.has(serviceSlug) && decision === 'go') {
    actions.push('Thu GSC/GA4 read access trước buổi Consult');
  }
  const gate = String(readiness.consult_gate_level ?? '');
  if (gate === 'warn' && decision === 'go') {
    actions.push(`BANT ${readiness.bant_total ?? 0}/30 — cân nhắc bổ sung qualify trước báo giá`);
  }
  if (actions.length === 0 && decision === 'go') {
    actions.push('Tiếp tục audit Consult — dùng task form + AI assist');
  }
  return actions.slice(0, 6);
}

export function toIntakeSessionBriefRow(session: IntakeSessionRow): IntakeSessionBriefRow {
  return {
    id: session.id,
    mode: session.mode,
    status: session.status,
    bant_total: session.bant_total,
    decision: session.decision,
    decision_reason: session.decision_reason,
    ai_summary: session.ai_summary,
    next_meeting_at: session.next_meeting_at,
    proposal_date: session.proposal_date,
    completed_at: session.completed_at,
    lead_temperature: session.lead_temperature,
  };
}

export function buildConsultBrief(input: {
  lifecycleId: number;
  serviceSlug: string;
  leadId: number | null;
  leadTaskDone: boolean;
  leadTask: { task_id: number; form_data: Record<string, unknown>; notes: string; is_done: boolean } | null;
  intakeSessions: IntakeSessionRow[];
}): Record<string, unknown> {
  const slug = input.serviceSlug;
  const intakeSessions = input.intakeSessions.map(toIntakeSessionBriefRow);
  const latestRaw = latestCompleted(input.intakeSessions);
  const latestPublic = latestRaw
    ? intakeSessions.find((s) => s.id === latestRaw.id) ?? intakeSessions[0] ?? null
    : null;

  let stakeholders: unknown[] = [];
  let commitments: unknown[] = [];
  let redFlags: string[] = [];
  if (latestRaw) {
    stakeholders = Array.isArray(latestRaw.stakeholders_json) ? latestRaw.stakeholders_json : [];
    commitments = Array.isArray(latestRaw.commitments_json) ? latestRaw.commitments_json : [];
    redFlags = extractRedFlags(latestRaw);
  }

  const decision = String(latestPublic?.decision ?? '');
  const bantTotal = Number(latestPublic?.bant_total ?? 0);
  const gateLevel = consultGateLevel(decision, bantTotal);

  const readiness = {
    lead_task_done: input.leadTaskDone,
    has_any_intake: intakeSessions.some((s) => s.status === 'completed'),
    has_intake_phone: hasCompletedMode(intakeSessions, 'phone'),
    has_intake_in_person: hasCompletedMode(intakeSessions, 'in_person'),
    decision,
    decision_label: DECISION_LABELS[decision] ?? (decision || '—'),
    bant_total: bantTotal,
    lead_temperature: String(latestPublic?.lead_temperature ?? ''),
    temperature_label: TEMPERATURE_LABELS[String(latestPublic?.lead_temperature ?? '')] ?? '—',
    can_advance_from_lead: input.leadTaskDone && decision === 'go',
    consult_gate_level: gateLevel,
  };

  const brief: Record<string, unknown> = {
    lifecycle_id: input.lifecycleId,
    service_slug: slug,
    service_label: SERVICE_LABELS[slug] ?? slug,
    lead_id: input.leadId,
    readiness,
    highlights: buildHighlights(input.leadTask, latestRaw),
    lead_task: input.leadTask,
    intake_sessions: intakeSessions,
    stakeholders,
    commitments,
    red_flags: redFlags,
    recommended_actions: [],
    latest_intake_summary: buildLatestIntakeSummary(latestRaw),
  };
  brief.recommended_actions = buildRecommendedActions(brief);
  return brief;
}

function formatMappedValue(sourceKey: string, value: unknown, targetKey: string): string {
  const text = String(value ?? '').trim();
  if (!text) return '';
  if ((sourceKey === 'need' || sourceKey === '_pain_summary') && targetKey === 'current_status') {
    if (text.toLowerCase().startsWith('pain:')) return text.slice(0, 4000);
    return `Pain: ${text}`.slice(0, 4000);
  }
  if (sourceKey === 'domain' && targetKey === 'current_status') {
    return `Domain: ${text}`.slice(0, 4000);
  }
  if (['platform', 'urgency', 'gbp_status', 'has_ads_account', 'has_google_ads'].includes(sourceKey)) {
    const label = sourceKey.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
    return `${label}: ${text}`.slice(0, 4000);
  }
  return text.slice(0, 4000);
}

function collectSourceValues(
  leadForm: Record<string, unknown>,
  intakeSession: IntakeSessionRow | null,
): Record<string, unknown> {
  const sources: Record<string, unknown> = { ...leadForm };
  if (!intakeSession) return sources;
  const answers = intakeSession.answers_json ?? {};
  const crm = answers.crm_fields;
  if (crm && typeof crm === 'object') {
    for (const [key, val] of Object.entries(crm as Record<string, unknown>)) {
      if (!fieldEmpty(val) && fieldEmpty(sources[key])) sources[key] = val;
    }
  }
  const meta = answers.meta;
  if (meta && typeof meta === 'object') {
    const pain = String((meta as Record<string, unknown>).pain_summary ?? '').trim();
    if (pain && fieldEmpty(sources.need)) sources._pain_summary = pain;
  }
  return sources;
}

function extractIntakeKeywordHints(intakeSession: IntakeSessionRow | null): string {
  if (!intakeSession) return '';
  const answers = intakeSession.answers_json ?? {};
  const phone = answers.phone;
  if (!phone || typeof phone !== 'object') return '';
  const snippets: string[] = [];
  const keys = Object.keys(phone as Record<string, unknown>).sort((a, b) => {
    const na = a.startsWith('p') && /^\d+$/.test(a.slice(1)) ? Number(a.slice(1)) : 999;
    const nb = b.startsWith('p') && /^\d+$/.test(b.slice(1)) ? Number(b.slice(1)) : 999;
    return na - nb;
  });
  for (const key of keys) {
    const val = String((phone as Record<string, unknown>)[key] ?? '').trim();
    if (!val) continue;
    const plain = val.replace(/[<>]/g, ' ');
    snippets.push(plain.length > 160 ? `${plain.slice(0, 157)}…` : plain);
    if (snippets.length >= 6) break;
  }
  return snippets.join('\n').slice(0, 4000);
}

function appendNoteLines(existing: string, lines: string[]): string {
  let text = String(existing ?? '').trim();
  for (const line of lines) {
    const snippet = String(line ?? '').trim();
    if (!snippet || text.includes(snippet)) continue;
    text = text ? `${text}\n${snippet}` : snippet;
  }
  return text.slice(0, 4000);
}

export function prefillConsultTaskForm(input: {
  serviceSlug: string;
  consultTask: SvcTaskRow;
  leadTask: SvcTaskRow | null;
  latestIntake: IntakeSessionRow | null;
  overwrite: boolean;
}): {
  form_data: Record<string, unknown>;
  notes: string;
  filled: string[];
  skipped_existing: string[];
} {
  const slug = input.serviceSlug;
  const leadForm = input.leadTask?.form_data ?? {};
  const sources = collectSourceValues(leadForm, input.latestIntake);
  const fieldMap = getCrmFieldMap(slug);
  const formData = { ...input.consultTask.form_data };
  const filled: string[] = [];
  const skipped: string[] = [];

  const setField = (targetKey: string, rawValue: unknown, sourceKey = ''): void => {
    if (fieldEmpty(rawValue)) return;
    const newVal = sourceKey
      ? formatMappedValue(sourceKey || targetKey, rawValue, targetKey)
      : String(rawValue).trim().slice(0, 4000);
    if (!newVal) return;
    const existing = formData[targetKey];
    if (!input.overwrite && !fieldEmpty(existing)) {
      if (!skipped.includes(targetKey)) skipped.push(targetKey);
      return;
    }
    if (targetKey === 'current_status' && !fieldEmpty(existing) && input.overwrite) {
      const merged = `${existing}\n${newVal}`.slice(0, 4000);
      if (merged !== existing) {
        formData[targetKey] = merged;
        filled.push(targetKey);
      }
      return;
    }
    if (String(existing ?? '') !== newVal) {
      formData[targetKey] = newVal;
      filled.push(targetKey);
    }
  };

  const pain = sources.need ?? sources._pain_summary;
  if (pain) setField('current_status', pain, 'need');

  for (const [sourceKey, targetKey] of Object.entries(fieldMap)) {
    if (sourceKey === 'need' || sourceKey === '_pain_summary') continue;
    if (!(sourceKey in sources)) continue;
    setField(targetKey, sources[sourceKey], sourceKey);
  }

  if (SEO_SLUGS.has(slug) || slug === 'quang-cao-google') {
    const kwHint = extractIntakeKeywordHints(input.latestIntake);
    if (kwHint) setField('target_keywords', kwHint);
  }

  const noteLines: string[] = [];
  const niche = String(sources.niche ?? '').trim();
  const budget = sources.budget ?? sources.monthly_budget ?? sources.daily_budget;
  if (niche) noteLines.push(`Ngành: ${niche}`);
  if (budget != null && budget !== '') {
    const n = Number(budget);
    noteLines.push(Number.isFinite(n) ? `NS: ${n.toLocaleString('vi-VN')} VND` : `NS: ${budget} VND`);
  }
  if (input.latestIntake?.decision) {
    noteLines.push(
      `Intake #${input.latestIntake.id}: ${input.latestIntake.decision} BANT ${input.latestIntake.bant_total}/30`,
    );
  }

  const notes = appendNoteLines(input.consultTask.notes, noteLines);
  return {
    form_data: formData,
    notes,
    filled: [...new Set(filled)].sort(),
    skipped_existing: [...new Set(skipped)].sort(),
  };
}
