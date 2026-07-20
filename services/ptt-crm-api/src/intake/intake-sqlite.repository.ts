import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { DatabaseSync } from 'node:sqlite';
import { catalogTs } from '../catalog/catalog-slug.util';
import { AppConfigService } from '../config/app-config.service';
import {
  BANT_KEYS,
  COMMON_FORM_SLUG,
  isCommonSlug,
  normalizeIntakeSlug,
  resolveDefinitionSlug,
} from './intake-definitions.util';
import {
  CreateIntakeSessionBody,
  IntakeEntryResult,
  IntakeSessionRow,
  IntakeStatsResult,
  PatchIntakeSessionBody,
  STAKEHOLDER_ROLES,
  VALID_DECISIONS,
  VALID_MODES,
  VALID_STATUS,
  VALID_TEMPERATURES,
} from './intake.types';

interface SqliteIntakeRow {
  id: number;
  lead_id: number | null;
  lifecycle_id: number | null;
  service_slug: string;
  mode: string;
  status: string;
  am_id: number | null;
  contact_name: string;
  contact_role: string;
  company_name: string;
  source: string;
  bant_json: string;
  bant_total: number;
  lead_temperature: string;
  decision: string;
  decision_reason: string;
  answers_json: string;
  stakeholders_json: string;
  commitments_json: string;
  next_meeting_at: string;
  next_meeting_note: string;
  proposal_date: string;
  ai_summary: string;
  ai_suggested_questions: string;
  started_at: string;
  completed_at: string;
  created_at: string;
  updated_at: string;
}

@Injectable()
export class IntakeSqliteRepository implements OnModuleDestroy {
  private db: DatabaseSync | null = null;

  constructor(private readonly config: AppConfigService) {}

  private get database(): DatabaseSync {
    if (!this.db) {
      this.db = new DatabaseSync(this.config.sqlitePath);
      this.db.exec('PRAGMA foreign_keys = ON');
    }
    return this.db;
  }

  onModuleDestroy(): void {
    if (this.db) {
      this.db.close();
      this.db = null;
    }
  }

  listSessions(opts: { lifecycleId?: number; leadId?: number; limit?: number }): IntakeSessionRow[] {
    const limit = Math.max(1, Math.min(opts.limit ?? 20, 100));
    let rows: SqliteIntakeRow[];
    if (opts.lifecycleId) {
      rows = this.database
        .prepare(
          `SELECT * FROM crm_lead_intake_sessions
           WHERE lifecycle_id = ?
           ORDER BY updated_at DESC, id DESC
           LIMIT ?`,
        )
        .all(opts.lifecycleId, limit) as unknown as SqliteIntakeRow[];
    } else if (opts.leadId) {
      rows = this.database
        .prepare(
          `SELECT * FROM crm_lead_intake_sessions
           WHERE lead_id = ?
           ORDER BY updated_at DESC, id DESC
           LIMIT ?`,
        )
        .all(opts.leadId, limit) as unknown as SqliteIntakeRow[];
    } else {
      return [];
    }
    return rows.map((r) => this.mapSession(r));
  }

  getSession(sessionId: number): IntakeSessionRow | null {
    const row = this.database
      .prepare('SELECT * FROM crm_lead_intake_sessions WHERE id = ?')
      .get(sessionId) as unknown as SqliteIntakeRow | undefined;
    return row ? this.mapSession(row) : null;
  }

  createSession(body: CreateIntakeSessionBody): IntakeSessionRow {
    const lifecycleId = body.lifecycle_id ?? null;
    let leadId = body.lead_id ?? null;
    if (!lifecycleId && !leadId) {
      throw new Error('lifecycle_id hoặc lead_id bắt buộc');
    }

    let serviceSlug = normalizeIntakeSlug(body.service_slug ?? '') || COMMON_FORM_SLUG;
    if (!body.service_slug && lifecycleId) {
      const lcRow = this.database
        .prepare('SELECT service_slug FROM crm_service_lifecycle WHERE id = ?')
        .get(lifecycleId) as unknown as { service_slug: string } | undefined;
      if (lcRow) {
        serviceSlug = normalizeIntakeSlug(String(lcRow.service_slug ?? '')) || COMMON_FORM_SLUG;
      }
    }

    let mode = String(body.mode ?? 'phone').trim();
    if (!VALID_MODES.has(mode)) mode = 'phone';

    if (!leadId && lifecycleId) {
      leadId = this.resolveLeadId(lifecycleId, null);
    }

    const ts = catalogTs();
    const stakeholders = JSON.stringify(this.defaultStakeholders());
    const commitments = JSON.stringify(this.defaultCommitments());

    const result = this.database
      .prepare(
        `INSERT INTO crm_lead_intake_sessions (
           lead_id, lifecycle_id, service_slug, mode, status, am_id,
           contact_name, contact_role, company_name, source,
           bant_json, bant_total, stakeholders_json, commitments_json,
           answers_json, started_at, created_at, updated_at
         ) VALUES (?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?, '{}', 0, ?, ?, '{}', ?, ?, ?)`,
      )
      .run(
        leadId,
        lifecycleId,
        String(serviceSlug).trim(),
        mode,
        body.am_id ?? null,
        String(body.contact_name ?? '').slice(0, 500),
        String(body.contact_role ?? '').slice(0, 200),
        String(body.company_name ?? '').slice(0, 500),
        String(body.source ?? '').slice(0, 200),
        stakeholders,
        commitments,
        ts,
        ts,
        ts,
      );

    const sessionId = Number(result.lastInsertRowid);
    this.prefillSession(sessionId, { lifecycleId, leadId, mode });
    const session = this.getSession(sessionId);
    if (!session) throw new Error('Failed to create intake session');
    return session;
  }

  updateSession(sessionId: number, payload: PatchIntakeSessionBody): IntakeSessionRow | null {
    const prev = this.getSession(sessionId);
    if (!prev) return null;

    const merged: IntakeSessionRow = { ...prev };

    const scalarFields = [
      'mode',
      'contact_name',
      'contact_role',
      'company_name',
      'source',
      'lead_temperature',
      'decision',
      'decision_reason',
      'next_meeting_at',
      'next_meeting_note',
      'proposal_date',
      'status',
    ] as const;

    for (const field of scalarFields) {
      if (!(field in payload)) continue;
      const val = payload[field];
      if (field === 'mode' && !VALID_MODES.has(String(val))) continue;
      if (field === 'decision' && !VALID_DECISIONS.has(String(val))) continue;
      if (field === 'lead_temperature' && !VALID_TEMPERATURES.has(String(val))) continue;
      if (field === 'status' && !VALID_STATUS.has(String(val))) continue;
      const nextVal = typeof val === 'string' ? String(val).slice(0, 4000) : val;
      switch (field) {
        case 'mode':
          merged.mode = String(nextVal);
          break;
        case 'contact_name':
          merged.contact_name = String(nextVal);
          break;
        case 'contact_role':
          merged.contact_role = String(nextVal);
          break;
        case 'company_name':
          merged.company_name = String(nextVal);
          break;
        case 'source':
          merged.source = String(nextVal);
          break;
        case 'lead_temperature':
          merged.lead_temperature = String(nextVal);
          break;
        case 'decision':
          merged.decision = String(nextVal);
          break;
        case 'decision_reason':
          merged.decision_reason = String(nextVal);
          break;
        case 'next_meeting_at':
          merged.next_meeting_at = String(nextVal);
          break;
        case 'next_meeting_note':
          merged.next_meeting_note = String(nextVal);
          break;
        case 'proposal_date':
          merged.proposal_date = String(nextVal);
          break;
        case 'status':
          merged.status = String(nextVal);
          break;
      }
    }

    if (payload.bant_json && typeof payload.bant_json === 'object') {
      merged.bant_json = payload.bant_json;
    }
    if (payload.answers_json && typeof payload.answers_json === 'object') {
      merged.answers_json = payload.answers_json;
    }
    if (payload.stakeholders_json && Array.isArray(payload.stakeholders_json)) {
      merged.stakeholders_json = payload.stakeholders_json;
    }
    if (payload.commitments_json && Array.isArray(payload.commitments_json)) {
      merged.commitments_json = payload.commitments_json;
    }

    merged.bant_total = this.computeBantTotal(merged.bant_json);

    const ts = catalogTs();
    this.database
      .prepare(
        `UPDATE crm_lead_intake_sessions SET
           mode = ?, contact_name = ?, contact_role = ?, company_name = ?, source = ?,
           bant_json = ?, bant_total = ?, lead_temperature = ?, decision = ?, decision_reason = ?,
           answers_json = ?, stakeholders_json = ?, commitments_json = ?,
           next_meeting_at = ?, next_meeting_note = ?, proposal_date = ?,
           status = ?, updated_at = ?
         WHERE id = ?`,
      )
      .run(
        merged.mode || 'phone',
        String(merged.contact_name ?? '').slice(0, 500),
        String(merged.contact_role ?? '').slice(0, 200),
        String(merged.company_name ?? '').slice(0, 500),
        String(merged.source ?? '').slice(0, 200),
        JSON.stringify(merged.bant_json ?? {}),
        Number(merged.bant_total ?? 0),
        String(merged.lead_temperature ?? '').slice(0, 20),
        String(merged.decision ?? '').slice(0, 20),
        String(merged.decision_reason ?? '').slice(0, 4000),
        JSON.stringify(merged.answers_json ?? {}).slice(0, 500000),
        JSON.stringify(merged.stakeholders_json ?? []).slice(0, 50000),
        JSON.stringify(merged.commitments_json ?? []).slice(0, 50000),
        String(merged.next_meeting_at ?? '').slice(0, 50),
        String(merged.next_meeting_note ?? '').slice(0, 4000),
        String(merged.proposal_date ?? '').slice(0, 50),
        String(merged.status ?? 'draft').slice(0, 20),
        ts,
        sessionId,
      );

    return this.getSession(sessionId);
  }

  completeSession(sessionId: number, actorId: number | null): IntakeSessionRow | null {
    const session = this.getSession(sessionId);
    if (!session) return null;
    if (!String(session.decision ?? '').trim()) {
      throw new Error('Cần chọn quyết định Go / Nurture / No-Go trước khi hoàn thành');
    }

    const ts = catalogTs();
    this.database
      .prepare(
        `UPDATE crm_lead_intake_sessions
         SET status = 'completed', completed_at = ?, updated_at = ?
         WHERE id = ?`,
      )
      .run(ts, ts, sessionId);

    const completed = this.getSession(sessionId);
    if (!completed) return null;

    this.syncCommonIntakeToLead(completed);
    this.logIntakeActivity(completed, actorId);
    return this.getSession(sessionId);
  }

  hasLifecycleTable(): boolean {
    const row = this.database
      .prepare("SELECT 1 FROM sqlite_master WHERE type='table' AND name='crm_service_lifecycle'")
      .get() as unknown as { 1: number } | undefined;
    return Boolean(row);
  }

  getIntakeStats(amId?: number, byAm = false): IntakeStatsResult {
    const lifecycleExists = this.hasLifecycleTable();
    let totalLifecycles = 0;
    let withCompletedIntake = 0;

    if (lifecycleExists) {
      const lcParams: number[] = [];
      let lcFilter = "status IN ('active', 'draft')";
      if (amId != null && Number.isFinite(amId)) {
        lcFilter += ' AND assigned_am = ?';
        lcParams.push(amId);
      }
      const totalRow = this.database
        .prepare(`SELECT COUNT(*) AS n FROM crm_service_lifecycle WHERE ${lcFilter}`)
        .get(...lcParams) as unknown as { n: number };
      totalLifecycles = Number(totalRow?.n ?? 0);

      const intakeLcFilter = lcFilter.replace('status IN', 'lc.status IN');
      const withRow = this.database
        .prepare(
          `SELECT COUNT(DISTINCT s.lifecycle_id) AS n
           FROM crm_lead_intake_sessions s
           INNER JOIN crm_service_lifecycle lc ON lc.id = s.lifecycle_id
           WHERE s.status = 'completed' AND s.lifecycle_id IS NOT NULL
             AND ${intakeLcFilter}`,
        )
        .get(...lcParams) as unknown as { n: number };
      withCompletedIntake = Number(withRow?.n ?? 0);
    }

    const sessionParams: number[] = [];
    let sessionFilter = "status = 'completed' AND lifecycle_id IS NOT NULL";
    if (amId != null && Number.isFinite(amId) && lifecycleExists) {
      sessionFilter +=
        " AND lifecycle_id IN (SELECT id FROM crm_service_lifecycle WHERE assigned_am = ? AND status IN ('active', 'draft'))";
      sessionParams.push(amId);
    }
    const completedRow = this.database
      .prepare(`SELECT COUNT(*) AS n FROM crm_lead_intake_sessions WHERE ${sessionFilter}`)
      .get(...sessionParams) as unknown as { n: number };
    const completedSessions = Number(completedRow?.n ?? 0);

    const avgRow = this.database
      .prepare(
        `SELECT ROUND(AVG(bant_total), 1) AS avg_bant
         FROM crm_lead_intake_sessions
         WHERE status = 'completed'`,
      )
      .get() as unknown as { avg_bant: number | null };
    const avgBantTotal = Number(avgRow?.avg_bant ?? 0);

    const coveragePct =
      totalLifecycles > 0 ? Math.round((withCompletedIntake / totalLifecycles) * 1000) / 10 : 0;

    const result: IntakeStatsResult = {
      total_lifecycles: totalLifecycles,
      lifecycles_with_completed_intake: withCompletedIntake,
      completed_intake_sessions: completedSessions,
      intake_coverage_pct: coveragePct,
      avg_bant_total: avgBantTotal,
      lifecycle_table_exists: lifecycleExists,
    };
    if (amId != null && Number.isFinite(amId)) {
      result.am_id = amId;
    }

    if (byAm && lifecycleExists) {
      const rows = this.database
        .prepare(
          `SELECT lc.assigned_am AS staff_id,
                  st.name AS name,
                  COUNT(DISTINCT lc.id) AS lifecycle_count,
                  COUNT(DISTINCT CASE WHEN s.status = 'completed' THEN lc.id END) AS intake_completed,
                  ROUND(AVG(CASE WHEN s.status = 'completed' THEN s.bant_total END), 1) AS avg_bant
           FROM crm_service_lifecycle lc
           INNER JOIN crm_staff st ON st.id = lc.assigned_am
           LEFT JOIN crm_lead_intake_sessions s
             ON s.lifecycle_id = lc.id AND s.status = 'completed'
           WHERE lc.status IN ('active', 'draft')
             AND lc.assigned_am IS NOT NULL
           GROUP BY lc.assigned_am, st.name
           ORDER BY intake_completed DESC, st.name`,
        )
        .all() as unknown as Array<Record<string, unknown>>;
      result.by_am = rows.map((r) => ({
        staff_id: Number(r.staff_id),
        name: String(r.name ?? ''),
        lifecycle_count: Number(r.lifecycle_count ?? 0),
        intake_completed: Number(r.intake_completed ?? 0),
        avg_bant: Number(r.avg_bant ?? 0),
      }));
    }

    return result;
  }

  resolveIntakeEntry(leadId: number, modeRaw?: string, formRaw?: string): IntakeEntryResult {
    let mode = String(modeRaw ?? 'phone').trim();
    if (!VALID_MODES.has(mode)) mode = 'phone';
    const formKey = String(formRaw ?? '').trim().toLowerCase();
    const forceCommon = ['common', '_common', '1', 'true', 'yes', 'chung'].includes(formKey);

    if (!this.hasLifecycleTable() || forceCommon) {
      return {
        ok: true,
        lead_id: leadId,
        lifecycle_id: null,
        service_slug: COMMON_FORM_SLUG,
        is_common_form: true,
        redirect_url: `/crm/intake?lead_id=${leadId}&mode=${mode}&service_slug=${COMMON_FORM_SLUG}&auto_create=1`,
      };
    }

    const lcRow = this.database
      .prepare('SELECT * FROM crm_service_lifecycle WHERE lead_id = ? ORDER BY id DESC LIMIT 1')
      .get(leadId) as unknown as { id: number; service_slug: string } | undefined;

    if (!lcRow) {
      return {
        ok: true,
        lead_id: leadId,
        lifecycle_id: null,
        service_slug: COMMON_FORM_SLUG,
        is_common_form: true,
        redirect_url: `/crm/intake?lead_id=${leadId}&mode=${mode}&service_slug=${COMMON_FORM_SLUG}&auto_create=1`,
      };
    }

    const slug = String(lcRow.service_slug ?? '').trim();
    const defSlug = resolveDefinitionSlug(slug);
    const isCommon = defSlug === COMMON_FORM_SLUG;
    let params = `lifecycle_id=${lcRow.id}&mode=${mode}&auto_create=1`;
    if (isCommon) {
      params += `&service_slug=${COMMON_FORM_SLUG}`;
    }
    return {
      ok: true,
      lifecycle_id: lcRow.id,
      lead_id: leadId,
      service_slug: isCommon ? COMMON_FORM_SLUG : slug,
      is_common_form: isCommon,
      redirect_url: `/crm/intake?${params}`,
    };
  }

  reopenSession(sessionId: number): IntakeSessionRow | null {
    const ts = catalogTs();
    this.database
      .prepare(
        `UPDATE crm_lead_intake_sessions
         SET status = 'draft', completed_at = '', updated_at = ?
         WHERE id = ?`,
      )
      .run(ts, sessionId);
    return this.getSession(sessionId);
  }

  saveAiSummaryStub(sessionId: number): IntakeSessionRow | null {
    const session = this.getSession(sessionId);
    if (!session) return null;
    const parts = [
      `Intake #${session.id}`,
      session.contact_name ? `Liên hệ: ${session.contact_name}` : '',
      session.company_name ? `Công ty: ${session.company_name}` : '',
      `BANT ${session.bant_total ?? 0}/30`,
      session.decision ? `Quyết định: ${session.decision}` : '',
      session.decision_reason ? `Lý do: ${session.decision_reason.slice(0, 500)}` : '',
    ].filter(Boolean);
    const summary = parts.join(' · ').slice(0, 4000);
    const ts = catalogTs();
    this.database
      .prepare(
        `UPDATE crm_lead_intake_sessions
         SET ai_summary = ?, updated_at = ?
         WHERE id = ?`,
      )
      .run(summary, ts, sessionId);
    return this.getSession(sessionId);
  }

  computeBantTotal(bantJson: Record<string, unknown>): number {
    let total = 0;
    for (const key of BANT_KEYS) {
      let score = 0;
      try {
        score = Number(bantJson[key] ?? 0);
      } catch {
        score = 0;
      }
      if (score >= 1 && score <= 5) total += score;
    }
    return total;
  }

  private resolveLeadId(lifecycleId: number | null, leadId: number | null): number | null {
    if (leadId) return leadId;
    if (!lifecycleId) return null;
    const row = this.database
      .prepare('SELECT lead_id FROM crm_service_lifecycle WHERE id = ?')
      .get(lifecycleId) as unknown as { lead_id: number | null } | undefined;
    return row?.lead_id != null ? Number(row.lead_id) : null;
  }

  private defaultStakeholders(): Array<Record<string, string>> {
    return STAKEHOLDER_ROLES.map(([role, label]) => ({
      role,
      role_label: label,
      name: '',
      title: '',
      influence: '',
      notes: '',
    }));
  }

  private defaultCommitments(): Array<Record<string, string>> {
    return [
      { label: 'Cam kết 1 — Thông tin', detail: '', deadline: '' },
      { label: 'Cam kết 2 — Thời gian', detail: '', deadline: '' },
      { label: 'Cam kết 3 — Ngân sách / quyết định', detail: '', deadline: '' },
    ];
  }

  private prefillSession(
    sessionId: number,
    opts: { lifecycleId?: number | null; leadId?: number | null; mode: string },
  ): void {
    const session = this.getSession(sessionId);
    if (!session) return;

    const payload: PatchIntakeSessionBody = {};
    const lid = this.resolveLeadId(opts.lifecycleId ?? null, opts.leadId ?? null);
    if (lid) {
      Object.assign(payload, this.fetchLeadPrefill(lid));
    }

    if (opts.mode === 'in_person' && (opts.lifecycleId ?? session.lifecycle_id)) {
      const lcId = opts.lifecycleId ?? session.lifecycle_id;
      const phoneSession = this.getLatestCompletedSession(Number(lcId), 'phone');
      if (phoneSession) {
        const recapText = this.buildRecapFromSession(phoneSession);
        const recapMeta = {
          phone_session_id: phoneSession.id,
          phone_completed_at: phoneSession.completed_at || '',
          recap: recapText,
        };
        if (phoneSession.contact_name) payload.contact_name = phoneSession.contact_name;
        if (phoneSession.company_name) payload.company_name = phoneSession.company_name;
        if (phoneSession.bant_json && !session.bant_total) {
          payload.bant_json = phoneSession.bant_json;
        }

        const existingAnswers =
          payload.answers_json && typeof payload.answers_json === 'object'
            ? payload.answers_json
            : session.answers_json || {};
        const mergedMeta = {
          ...((existingAnswers.meta as Record<string, unknown>) || {}),
          ...recapMeta,
        };
        payload.answers_json = {
          ...existingAnswers,
          meta: mergedMeta,
          recap: recapText,
        };
      }
    }

    if (Object.keys(payload).length > 0) {
      this.updateSession(sessionId, payload);
    }
  }

  private fetchLeadPrefill(leadId: number): PatchIntakeSessionBody {
    const row = this.database
      .prepare('SELECT full_name, need, source, meta_json FROM crm_leads WHERE id = ?')
      .get(leadId) as unknown as {
      full_name: string;
      need: string;
      source: string;
      meta_json: string;
    } | undefined;
    if (!row) return {};

    let meta: Record<string, unknown> = {};
    try {
      meta = JSON.parse(String(row.meta_json || '{}')) as Record<string, unknown>;
    } catch {
      meta = {};
    }
    const aiBrief =
      meta.ai_qualify_brief && typeof meta.ai_qualify_brief === 'object'
        ? (meta.ai_qualify_brief as Record<string, unknown>)
        : {};

    let pain = String(row.need ?? '').trim();
    if (!pain && typeof aiBrief.summary === 'string') {
      pain = aiBrief.summary.trim();
    }

    const metaBlock: Record<string, unknown> = {
      pain_summary: pain.slice(0, 4000),
      ai_brief: String(aiBrief.summary ?? '').slice(0, 4000),
    };
    if (aiBrief.service_slug) {
      metaBlock.qualify_service_slug = String(aiBrief.service_slug).slice(0, 120);
    }

    const crmFields: Record<string, string> = {};
    if (row.need) crmFields.need = String(row.need).slice(0, 4000);

    return {
      contact_name: String(row.full_name ?? '').slice(0, 500),
      source: String(row.source ?? '').slice(0, 200),
      answers_json: {
        meta: metaBlock,
        crm_fields: crmFields,
      },
    };
  }

  private getLatestCompletedSession(lifecycleId: number, mode: string): IntakeSessionRow | null {
    const row = this.database
      .prepare(
        `SELECT * FROM crm_lead_intake_sessions
         WHERE lifecycle_id = ? AND mode = ? AND status = 'completed'
         ORDER BY completed_at DESC, id DESC
         LIMIT 1`,
      )
      .get(lifecycleId, mode) as unknown as SqliteIntakeRow | undefined;
    return row ? this.mapSession(row) : null;
  }

  private buildRecapFromSession(phoneSession: IntakeSessionRow): string {
    const parts: string[] = [];
    if (phoneSession.contact_name) parts.push(`Liên hệ: ${phoneSession.contact_name}`);
    parts.push(`BANT ${phoneSession.bant_total ?? 0}/30`);
    if (phoneSession.decision) parts.push(`Quyết định: ${phoneSession.decision}`);

    const answers = phoneSession.answers_json || {};
    const meta =
      answers.meta && typeof answers.meta === 'object'
        ? (answers.meta as Record<string, unknown>)
        : {};
    if (meta.pain_summary) parts.push(`Pain: ${String(meta.pain_summary)}`);

    const phone =
      answers.phone && typeof answers.phone === 'object'
        ? (answers.phone as Record<string, string>)
        : {};
    const snippets: string[] = [];
    for (const key of Object.keys(phone).sort((a, b) => {
      const ai = a.startsWith('p') && /^\d+$/.test(a.slice(1)) ? Number(a.slice(1)) : 999;
      const bi = b.startsWith('p') && /^\d+$/.test(b.slice(1)) ? Number(b.slice(1)) : 999;
      return ai - bi;
    })) {
      const val = String(phone[key] ?? '').trim();
      if (val) {
        let plain = val.replace(/</g, ' ').replace(/>/g, ' ');
        if (plain.length > 120) plain = `${plain.slice(0, 117)}…`;
        snippets.push(plain);
      }
      if (snippets.length >= 4) break;
    }
    if (snippets.length) parts.push(`Ghi chú gọi: ${snippets.join(' · ')}`);
    return parts.join('\n').slice(0, 4000);
  }

  private syncCommonIntakeToLead(session: IntakeSessionRow): void {
    if (!isCommonSlug(String(session.service_slug ?? ''))) return;
    if (session.lifecycle_id) return;

    const leadId = this.resolveLeadId(session.lifecycle_id, session.lead_id);
    if (!leadId) return;

    const answers = session.answers_json || {};
    const crm =
      answers.crm_fields && typeof answers.crm_fields === 'object'
        ? (answers.crm_fields as Record<string, unknown>)
        : {};
    const meta =
      answers.meta && typeof answers.meta === 'object'
        ? (answers.meta as Record<string, unknown>)
        : {};
    const need = String(crm.need ?? meta.pain_summary ?? '').trim();
    if (!need) return;

    const row = this.database
      .prepare('SELECT need FROM crm_leads WHERE id = ?')
      .get(leadId) as unknown as { need: string } | undefined;
    if (!row) return;
    const prevNeed = String(row.need ?? '').trim();
    if (prevNeed) return;

    const ts = catalogTs();
    this.database
      .prepare('UPDATE crm_leads SET need = ?, updated_at = ? WHERE id = ?')
      .run(need.slice(0, 4000), ts, leadId);
  }

  private logIntakeActivity(session: IntakeSessionRow, actorId: number | null): void {
    const leadId = this.resolveLeadId(session.lifecycle_id, session.lead_id);
    if (!leadId) return;

    const mode = session.mode || 'phone';
    const modeVi = mode === 'phone' ? 'gọi điện' : 'gặp trực tiếp';
    const actType = mode === 'phone' ? 'call' : 'meeting';
    let content =
      `Lead Intake #${session.id} (${modeVi})` +
      (isCommonSlug(String(session.service_slug ?? '')) ? ' · Form chung' : '') +
      ` · BANT ${session.bant_total ?? 0}/30 · ${session.decision || '—'}`;
    if (session.decision_reason) {
      content += ` · ${String(session.decision_reason).slice(0, 200)}`;
    }

    let nextAction = '';
    let nextAt = '';
    if (mode === 'phone' && session.decision === 'go') {
      nextAction = 'Hẹn gặp KH (PHẦN B)';
      nextAt = String(session.next_meeting_at ?? '').slice(0, 40);
    }

    const ts = catalogTs();
    const statusRow = this.database
      .prepare('SELECT status FROM crm_leads WHERE id = ?')
      .get(leadId) as unknown as { status: string } | undefined;
    const statusSnap = String(statusRow?.status ?? 'new');

    this.database
      .prepare(
        `INSERT INTO crm_lead_activities (
           lead_id, user_id, activity_type, content, result,
           next_action, next_action_at, created_at, created_by, lead_status_at_log
         ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        leadId,
        actorId,
        actType,
        content.slice(0, 8000),
        String(session.decision ?? '').slice(0, 500),
        nextAction.slice(0, 500),
        nextAt,
        ts,
        actorId ? String(actorId).slice(0, 120) : '',
        statusSnap,
      );

    this.database
      .prepare('UPDATE crm_leads SET updated_at = ? WHERE id = ?')
      .run(ts, leadId);
  }

  private parseJson<T>(raw: string, fallback: T): T {
    try {
      const val = JSON.parse(raw || '');
      return (val ?? fallback) as T;
    } catch {
      return fallback;
    }
  }

  private mapSession(row: SqliteIntakeRow): IntakeSessionRow {
    const rawQ = String(row.ai_suggested_questions ?? '').trim();
    let aiQuestions: string[] = [];
    if (rawQ.startsWith('[')) {
      aiQuestions = this.parseJson<string[]>(rawQ, []);
    } else if (rawQ) {
      aiQuestions = [rawQ];
    }

    return {
      id: Number(row.id),
      lead_id: row.lead_id != null ? Number(row.lead_id) : null,
      lifecycle_id: row.lifecycle_id != null ? Number(row.lifecycle_id) : null,
      service_slug: String(row.service_slug ?? ''),
      mode: String(row.mode ?? 'phone'),
      status: String(row.status ?? 'draft'),
      am_id: row.am_id != null ? Number(row.am_id) : null,
      contact_name: String(row.contact_name ?? ''),
      contact_role: String(row.contact_role ?? ''),
      company_name: String(row.company_name ?? ''),
      source: String(row.source ?? ''),
      bant_json: this.parseJson<Record<string, unknown>>(String(row.bant_json ?? ''), {}),
      bant_total: Number(row.bant_total ?? 0),
      lead_temperature: String(row.lead_temperature ?? ''),
      decision: String(row.decision ?? ''),
      decision_reason: String(row.decision_reason ?? ''),
      answers_json: this.parseJson<Record<string, unknown>>(String(row.answers_json ?? ''), {}),
      stakeholders_json: this.parseJson<Array<Record<string, string>>>(
        String(row.stakeholders_json ?? ''),
        [],
      ),
      commitments_json: this.parseJson<Array<Record<string, string>>>(
        String(row.commitments_json ?? ''),
        [],
      ),
      next_meeting_at: String(row.next_meeting_at ?? ''),
      next_meeting_note: String(row.next_meeting_note ?? ''),
      proposal_date: String(row.proposal_date ?? ''),
      ai_summary: String(row.ai_summary ?? ''),
      ai_suggested_questions: aiQuestions,
      started_at: String(row.started_at ?? ''),
      completed_at: String(row.completed_at ?? ''),
      created_at: String(row.created_at ?? ''),
      updated_at: String(row.updated_at ?? ''),
    };
  }
}
