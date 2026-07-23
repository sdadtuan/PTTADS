import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { DatabaseSync } from 'node:sqlite';
import { catalogTs } from '../catalog/catalog-slug.util';
import { AppConfigService } from '../config/app-config.service';
import {
  assertPresalesCareGate,
  CARE_PIPELINE_STAGES,
  CARE_STAGE_KEYS,
  CARE_STAGE_MIN_COMPLETION_NOTE_LEN,
  CONTACT_OK_CARE_STATUS,
  carePipelineState,
  parseLeadMeta,
  presalesCareGateState,
  serializeStagesDone,
} from './care-pipeline.util';
import {
  CompleteCareStageBody,
  LeadFunnelRow,
  LeadFunnelSnapshot,
  PatchMarketingPlanBody,
  PatchPresalesTaskBody,
  PresalesRow,
  PresalesSnapshot,
  PresalesTaskRow,
  ReleaseReviewQueueBody,
} from './leads-funnel.types';
import {
  defaultStrategyJson,
  planContentFromRow,
  validatePreliminaryPlan,
} from './presales-marketing-plan.util';
import { workflowStepsForService } from './presales-workflow-steps.util';
import {
  DEFAULT_B2_CONTACT_DEADLINE_HOURS,
  isLeadInReviewQueue,
  normalizeB2ContactDeadlineHours,
  REVIEW_QUEUE_REASON,
  reviewQueuePublicState,
} from './review-queue.util';
import { PRESALES_STAGES } from './leads-funnel.types';

@Injectable()
export class LeadsFunnelSqliteRepository implements OnModuleDestroy {
  private db: DatabaseSync | null = null;

  constructor(private readonly config: AppConfigService) {}

  private get database(): DatabaseSync {
    if (!this.db) {
      this.db = new DatabaseSync(this.config.sqlitePath);
      this.db.exec('PRAGMA foreign_keys = ON');
      this.ensureSchema();
    }
    return this.db;
  }

  onModuleDestroy(): void {
    if (this.db) {
      this.db.close();
      this.db = null;
    }
  }

  private ts(): string {
    return catalogTs();
  }

  ensureSchema(): void {
    const cols = this.database.prepare('PRAGMA table_info(crm_leads)').all() as Array<{ name: string }>;
    const colSet = new Set(cols.map((c) => c.name));
    if (!colSet.has('care_stage_current')) {
      this.database.exec(
        "ALTER TABLE crm_leads ADD COLUMN care_stage_current TEXT NOT NULL DEFAULT 'first_contact'",
      );
    }
    if (!colSet.has('care_stages_done_json')) {
      this.database.exec(
        "ALTER TABLE crm_leads ADD COLUMN care_stages_done_json TEXT NOT NULL DEFAULT '{}'",
      );
    }
    this.database.exec(`
      CREATE TABLE IF NOT EXISTS crm_lead_presales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id INTEGER NOT NULL UNIQUE REFERENCES crm_leads(id) ON DELETE CASCADE,
        service_slug TEXT NOT NULL DEFAULT '',
        stage TEXT NOT NULL DEFAULT 'lead',
        status TEXT NOT NULL DEFAULT 'active',
        assigned_am INTEGER REFERENCES crm_staff(id) ON DELETE SET NULL,
        lifecycle_id INTEGER,
        stage_entered_at TEXT NOT NULL DEFAULT '',
        notes TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL DEFAULT '',
        draft_marketing_plan_id INTEGER
      )
    `);
    this.database.exec(`
      CREATE TABLE IF NOT EXISTS crm_lead_presales_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        presales_id INTEGER NOT NULL REFERENCES crm_lead_presales(id) ON DELETE CASCADE,
        stage TEXT NOT NULL DEFAULT '',
        step_index INTEGER NOT NULL DEFAULT 0,
        title TEXT NOT NULL DEFAULT '',
        description TEXT NOT NULL DEFAULT '',
        form_fields TEXT NOT NULL DEFAULT '[]',
        form_data TEXT NOT NULL DEFAULT '{}',
        ai_output TEXT NOT NULL DEFAULT '',
        ai_prompt_key TEXT NOT NULL DEFAULT '',
        is_done INTEGER NOT NULL DEFAULT 0,
        done_at TEXT NOT NULL DEFAULT '',
        done_by INTEGER,
        notes TEXT NOT NULL DEFAULT '',
        is_custom INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL DEFAULT ''
      )
    `);
    this.database.exec(`
      CREATE TABLE IF NOT EXISTS crm_lead_settings (
        config_key TEXT PRIMARY KEY,
        config_json TEXT NOT NULL DEFAULT '{}',
        updated_at TEXT NOT NULL DEFAULT '',
        updated_by TEXT NOT NULL DEFAULT ''
      )
    `);
    this.database.exec(`
      CREATE TABLE IF NOT EXISTS crm_marketing_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL DEFAULT '',
        name TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'draft',
        plan_kind TEXT NOT NULL DEFAULT 'preliminary',
        lead_id INTEGER,
        presales_id INTEGER,
        north_star TEXT NOT NULL DEFAULT '',
        objectives TEXT NOT NULL DEFAULT '',
        strategy_framework_json TEXT NOT NULL DEFAULT '{}',
        target_market_prof_json TEXT NOT NULL DEFAULT '{}',
        target_market_steps4_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL DEFAULT ''
      )
    `);
  }

  fetchLeadConfig(): { b2_review_queue_enabled: boolean; b2_contact_deadline_hours: number } {
    const row = this.database
      .prepare("SELECT config_json FROM crm_lead_settings WHERE config_key = 'global'")
      .get() as { config_json: string } | undefined;
    let cfg: Record<string, unknown> = {};
    if (row?.config_json) {
      try {
        cfg = JSON.parse(row.config_json) as Record<string, unknown>;
      } catch {
        cfg = {};
      }
    }
    return {
      b2_review_queue_enabled: cfg.b2_review_queue_enabled !== false,
      b2_contact_deadline_hours: normalizeB2ContactDeadlineHours(
        cfg.b2_contact_deadline_hours ?? DEFAULT_B2_CONTACT_DEADLINE_HOURS,
      ),
    };
  }

  fetchLeadRow(leadId: number): LeadFunnelRow | null {
    const row = this.database
      .prepare(
        `SELECT l.id, l.full_name, l.phone, l.email, l.status, l.owner_id,
                l.meta_json, l.care_stage_current, l.care_stages_done_json,
                COALESCE(l.is_duplicate, 0) AS is_duplicate, l.updated_at,
                (
                  SELECT al.created_at FROM crm_lead_assignment_logs al
                  WHERE al.lead_id = l.id AND al.to_user_id IS NOT NULL
                  ORDER BY al.created_at ASC LIMIT 1
                ) AS first_assigned_at
         FROM crm_leads l WHERE l.id = ?`,
      )
      .get(leadId) as unknown as LeadFunnelRow | undefined;
    return row ?? null;
  }

  buildSnapshot(leadId: number, presalesEnabled: boolean): LeadFunnelSnapshot | null {
    const row = this.fetchLeadRow(leadId);
    if (!row) return null;
    const meta = parseLeadMeta(row.meta_json);
    const presales = presalesEnabled ? this.getPresalesSnapshot(leadId) : null;
    return {
      lead_id: leadId,
      care_pipeline: carePipelineState(row.status, row.care_stage_current, row.care_stages_done_json),
      presales_care_gate: presalesCareGateState(row.care_stage_current, row.care_stages_done_json),
      review_queue: reviewQueuePublicState(meta, row.first_assigned_at || row.updated_at || ''),
      presales_on_lead_enabled: presalesEnabled,
      presales,
    };
  }

  assertNotInReviewQueue(leadId: number): void {
    const row = this.fetchLeadRow(leadId);
    if (!row) throw new Error('Không tìm thấy lead.');
    if (isLeadInReviewQueue(parseLeadMeta(row.meta_json))) {
      throw new Error('Lead đang ở danh mục Phải tra soát — chỉ GDKD được xử lý.');
    }
  }

  submitCareReport(
    leadId: number,
    body: CompleteCareStageBody,
    actor: string,
    userId: number | null,
  ): void {
    this.assertNotInReviewQueue(leadId);
    const row = this.fetchLeadRow(leadId);
    if (!row) throw new Error('Không tìm thấy lead.');
    const stageKey = String(body.stage || 'first_contact').trim();
    if (!CARE_STAGE_KEYS.includes(stageKey)) {
      throw new Error('Bước chăm sóc không hợp lệ.');
    }
    const careStatus = String(body.care_status || CONTACT_OK_CARE_STATUS).trim();
    const ts = this.ts();
    this.database
      .prepare(
        `INSERT INTO crm_lead_activities (
           lead_id, user_id, activity_type, content, result,
           next_action, next_action_at, created_at, created_by,
           lead_status_at_log, care_status, care_stage_key, care_contact_type
         ) VALUES (?, ?, 'call', ?, '', '', '', ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        leadId,
        userId,
        String(body.content || 'Báo cáo chăm sóc B2').slice(0, 8000),
        ts,
        actor.slice(0, 120),
        row.status,
        careStatus,
        stageKey,
        String(body.care_contact_type || 'phone').slice(0, 80),
      );
    this.database
      .prepare('UPDATE crm_leads SET updated_at = ?, updated_by = ? WHERE id = ?')
      .run(ts, actor.slice(0, 120), leadId);
  }

  completeCareStage(leadId: number, body: CompleteCareStageBody, actor: string): LeadFunnelRow {
    this.assertNotInReviewQueue(leadId);
    const row = this.fetchLeadRow(leadId);
    if (!row) throw new Error('Không tìm thấy lead.');
    const key = String(body.stage || 'first_contact').trim();
    if (!CARE_STAGE_KEYS.includes(key)) throw new Error('Bước chăm sóc không hợp lệ.');
    let current = String(row.care_stage_current || '').trim();
    if (!CARE_STAGE_KEYS.includes(current)) current = 'first_contact';
    if (key !== current) throw new Error('Chỉ có thể hoàn thành bước đang thực hiện.');
    const reportCount = this.database
      .prepare(
        `SELECT COUNT(*) AS c FROM crm_lead_activities
         WHERE lead_id = ? AND care_stage_key = ? AND activity_type != 'system'
           AND (trim(COALESCE(care_status, '')) != '' OR trim(COALESCE(care_contact_type, '')) != '')`,
      )
      .get(leadId, key) as { c: number };
    if (Number(reportCount.c) < 1) {
      throw new Error('Phải gửi ít nhất một báo cáo chăm sóc cho bước này trước khi hoàn thành.');
    }
    const okRow = this.database
      .prepare(
        `SELECT 1 FROM crm_lead_activities
         WHERE lead_id = ? AND care_stage_key = ? AND activity_type != 'system'
           AND trim(COALESCE(care_status, '')) = ?
         LIMIT 1`,
      )
      .get(leadId, key, CONTACT_OK_CARE_STATUS);
    if (!okRow) {
      throw new Error(
        'Phải có báo cáo trạng thái 「Liên hệ OK» (da_lien_he_thanh_cong) trước khi hoàn thành B2.',
      );
    }
    const noteClean = String(body.note || '').trim();
    if (noteClean.length < CARE_STAGE_MIN_COMPLETION_NOTE_LEN) {
      throw new Error(
        `Ghi chú hoàn thành bước là bắt buộc (tối thiểu ${CARE_STAGE_MIN_COMPLETION_NOTE_LEN} ký tự).`,
      );
    }
    const ts = this.ts();
    const done = JSON.parse(row.care_stages_done_json || '{}') as Record<string, string>;
    done[key] = ts;
    const stageMeta = CARE_PIPELINE_STAGES.find((s) => s.key === key)!;
    this.database
      .prepare(
        `INSERT INTO crm_lead_activities (lead_id, activity_type, content, created_at, created_by, lead_status_at_log)
         VALUES (?, 'system', ?, ?, ?, ?)`,
      )
      .run(
        leadId,
        `Hoàn thành bước: ${stageMeta.label}. Ghi chú: ${noteClean}`.slice(0, 8000),
        ts,
        actor.slice(0, 120),
        row.status,
      );
    this.database
      .prepare(
        `UPDATE crm_leads SET care_stage_current = ?, care_stages_done_json = ?,
         status = ?, updated_at = ?, updated_by = ? WHERE id = ?`,
      )
      .run(key, serializeStagesDone(done), stageMeta.status_on_complete, ts, actor.slice(0, 120), leadId);
    const updated = this.fetchLeadRow(leadId);
    if (!updated) throw new Error('Không tìm thấy lead.');
    return updated;
  }

  countReviewQueue(): number {
    const row = this.database
      .prepare(
        `SELECT COUNT(*) AS c FROM crm_leads l
         WHERE COALESCE(json_extract(l.meta_json, '$.review_queue.active'), '') = 'true'
           AND COALESCE(l.is_duplicate, 0) = 0`,
      )
      .get() as { c: number };
    return Number(row.c ?? 0);
  }

  listReviewQueue(limit = 50): LeadFunnelRow[] {
    const lim = Math.max(1, Math.min(limit, 200));
    return this.database
      .prepare(
        `SELECT l.id, l.full_name, l.phone, l.email, l.status, l.owner_id,
                l.meta_json, l.care_stage_current, l.care_stages_done_json,
                COALESCE(l.is_duplicate, 0) AS is_duplicate, l.updated_at,
                json_extract(l.meta_json, '$.review_queue.assigned_at') AS first_assigned_at
         FROM crm_leads l
         WHERE COALESCE(json_extract(l.meta_json, '$.review_queue.active'), '') = 'true'
           AND COALESCE(l.is_duplicate, 0) = 0
         ORDER BY json_extract(l.meta_json, '$.review_queue.queued_at') DESC, l.id DESC
         LIMIT ?`,
      )
      .all(lim) as unknown as LeadFunnelRow[];
  }

  syncReviewQueue(actor: string, dryRun = false): Record<string, unknown> {
    const cfg = this.fetchLeadConfig();
    if (!cfg.b2_review_queue_enabled) {
      return { enabled: false, queued: 0, scanned: 0, deadline_hours: cfg.b2_contact_deadline_hours };
    }
    const rows = this.database
      .prepare(
        `SELECT l.*, (
            SELECT al.created_at FROM crm_lead_assignment_logs al
            WHERE al.lead_id = l.id AND al.to_user_id IS NOT NULL
            ORDER BY al.created_at ASC LIMIT 1
          ) AS first_assigned_at
         FROM crm_leads l
         WHERE l.owner_id IS NOT NULL AND COALESCE(l.is_duplicate, 0) = 0
           AND l.status NOT IN ('lost')
           AND COALESCE(json_extract(l.meta_json, '$.review_queue.active'), '') != 'true'
           AND COALESCE(json_extract(l.care_stages_done_json, '$.first_contact'), '') = ''`,
      )
      .all() as unknown as LeadFunnelRow[];
    let queued = 0;
    const leadIds: number[] = [];
    const now = new Date();
    for (const row of rows) {
      const gate = presalesCareGateState(row.care_stage_current, row.care_stages_done_json);
      if (gate.complete) continue;
      const assignedAt = row.first_assigned_at || row.updated_at || '';
      const assignedDt = new Date(String(assignedAt).slice(0, 19).replace(' ', 'T') + 'Z');
      if (Number.isNaN(assignedDt.getTime())) continue;
      const elapsedH = (now.getTime() - assignedDt.getTime()) / 3600000;
      if (elapsedH < cfg.b2_contact_deadline_hours) continue;
      leadIds.push(row.id);
      if (dryRun) {
        queued += 1;
        continue;
      }
      this.queueLeadForReview(row.id, {
        actor,
        previousOwnerId: row.owner_id,
        assignedAt,
        deadlineHours: cfg.b2_contact_deadline_hours,
      });
      queued += 1;
    }
    return {
      enabled: true,
      dry_run: dryRun,
      queued,
      scanned: rows.length,
      deadline_hours: cfg.b2_contact_deadline_hours,
      lead_ids: leadIds,
    };
  }

  private queueLeadForReview(
    leadId: number,
    opts: {
      actor: string;
      previousOwnerId: number | null;
      assignedAt: string;
      deadlineHours: number;
    },
  ): void {
    const row = this.fetchLeadRow(leadId);
    if (!row) return;
    const meta = parseLeadMeta(row.meta_json);
    if (isLeadInReviewQueue(meta)) return;
    const ts = this.ts();
    meta.review_queue = {
      active: true,
      reason: REVIEW_QUEUE_REASON,
      queued_at: ts,
      previous_owner_id: opts.previousOwnerId,
      assigned_at: opts.assignedAt,
      deadline_hours: opts.deadlineHours,
    };
    this.database
      .prepare(
        `UPDATE crm_leads SET owner_id = NULL, meta_json = ?, updated_at = ?, updated_by = ? WHERE id = ?`,
      )
      .run(JSON.stringify(meta), ts, opts.actor.slice(0, 120), leadId);
    if (opts.previousOwnerId) {
      this.database
        .prepare(
          `INSERT INTO crm_lead_assignment_logs
           (lead_id, from_user_id, to_user_id, reason, created_by, created_at)
           VALUES (?, ?, NULL, ?, ?, ?)`,
        )
        .run(
          leadId,
          opts.previousOwnerId,
          'Quá hạn B2 — chuyển Lead Phải tra soát (GDKD)',
          opts.actor.slice(0, 120),
          ts,
        );
    }
  }

  releaseFromReviewQueue(leadId: number, body: ReleaseReviewQueueBody, actor: string): LeadFunnelRow {
    const row = this.fetchLeadRow(leadId);
    if (!row) throw new Error('Không tìm thấy lead.');
    const meta = parseLeadMeta(row.meta_json);
    const rq = meta.review_queue as Record<string, unknown> | undefined;
    if (!rq?.active) throw new Error('Lead không ở danh mục Phải tra soát.');
    const mode = String(body.mode || '').trim().toLowerCase();
    if (mode !== 'auto' && mode !== 'manual') throw new Error('mode phải là auto hoặc manual.');
    let targetOwner: number | null = null;
    if (mode === 'manual') {
      if (!body.owner_id) throw new Error('Chọn AM để gán lại.');
      const staff = this.database
        .prepare('SELECT id FROM crm_staff WHERE id = ? AND COALESCE(active, 1) = 1')
        .get(body.owner_id);
      if (!staff) throw new Error('AM không hợp lệ hoặc đã ngưng.');
      targetOwner = Number(body.owner_id);
    } else {
      const prev = rq.previous_owner_id ? Number(rq.previous_owner_id) : null;
      if (prev) {
        const staff = this.database
          .prepare('SELECT id FROM crm_staff WHERE id = ? AND COALESCE(active, 1) = 1')
          .get(prev);
        if (staff) targetOwner = prev;
      }
      if (!targetOwner) throw new Error('Không tìm được AM để gán lại (auto).');
    }
    const ts = this.ts();
    delete meta.review_queue;
    this.database
      .prepare(
        `UPDATE crm_leads SET owner_id = ?, meta_json = ?, updated_at = ?, updated_by = ? WHERE id = ?`,
      )
      .run(targetOwner, JSON.stringify(meta), ts, actor.slice(0, 120), leadId);
    this.database
      .prepare(
        `INSERT INTO crm_lead_assignment_logs
         (lead_id, from_user_id, to_user_id, reason, created_by, created_at)
         VALUES (?, NULL, ?, ?, ?, ?)`,
      )
      .run(
        leadId,
        targetOwner,
        String(body.note || 'GDKD release từ Phải tra soát').slice(0, 500),
        actor.slice(0, 120),
        ts,
      );
    const updated = this.fetchLeadRow(leadId);
    if (!updated) throw new Error('Không tìm thấy lead.');
    return updated;
  }

  ensurePresales(leadId: number, serviceSlug: string, actor: string): PresalesRow {
    this.assertNotInReviewQueue(leadId);
    const row = this.fetchLeadRow(leadId);
    if (!row) throw new Error('Không tìm thấy lead.');
    assertPresalesCareGate(row.care_stage_current, row.care_stages_done_json);
    const slug = String(serviceSlug || '').trim();
    if (!slug) throw new Error('Cần service_slug để tạo pre-sales');
    const existing = this.database
      .prepare('SELECT * FROM crm_lead_presales WHERE lead_id = ?')
      .get(leadId) as unknown as PresalesRow | undefined;
    if (existing) {
      if (existing.status === 'converted') return existing;
      this.seedPresalesTasks(existing.id, slug);
      return existing;
    }
    const ts = this.ts();
    const ownerId = row.owner_id;
    const result = this.database
      .prepare(
        `INSERT INTO crm_lead_presales
         (lead_id, service_slug, stage, status, assigned_am, stage_entered_at, notes, created_at, updated_at)
         VALUES (?, ?, 'lead', 'active', ?, ?, ?, ?, ?)`,
      )
      .run(leadId, slug, ownerId, ts, `Pre-sales tạo bởi ${actor}`.slice(0, 4000), ts, ts);
    const presalesId = Number(result.lastInsertRowid);
    this.seedPresalesTasks(presalesId, slug);
    const ps = this.database
      .prepare('SELECT * FROM crm_lead_presales WHERE id = ?')
      .get(presalesId) as unknown as PresalesRow;
    return ps;
  }

  private seedPresalesTasks(presalesId: number, serviceSlug: string): void {
    const existing = this.database
      .prepare(
        'SELECT COUNT(*) AS c FROM crm_lead_presales_tasks WHERE presales_id = ? AND is_custom = 0',
      )
      .get(presalesId) as { c: number };
    if (Number(existing.c) > 0) return;
    const steps = workflowStepsForService(serviceSlug);
    const ts = this.ts();
    for (const stage of PRESALES_STAGES) {
      const stageSteps = steps[stage] || [];
      stageSteps.forEach((step, idx) => {
        this.database
          .prepare(
            `INSERT INTO crm_lead_presales_tasks
             (presales_id, stage, step_index, title, description, ai_prompt_key, form_fields, form_data, is_done, is_custom, created_at, updated_at)
             VALUES (?, ?, ?, ?, ?, ?, ?, '{}', 0, 0, ?, ?)`,
          )
          .run(
            presalesId,
            stage,
            idx,
            step.title,
            step.description,
            step.ai_prompt_key || '',
            JSON.stringify(step.form_fields || []),
            ts,
            ts,
          );
      });
    }
  }

  getPresalesSnapshot(leadId: number): PresalesSnapshot | null {
    const ps = this.database
      .prepare('SELECT * FROM crm_lead_presales WHERE lead_id = ?')
      .get(leadId) as unknown as PresalesRow | undefined;
    if (!ps) return null;
    const taskRows = this.database
      .prepare(
        'SELECT * FROM crm_lead_presales_tasks WHERE presales_id = ? ORDER BY stage, step_index, id',
      )
      .all(ps.id) as Array<Record<string, unknown>>;
    const tasks: Record<string, PresalesTaskRow[]> = {};
    for (const raw of taskRows) {
      const stage = String(raw.stage);
      const task: PresalesTaskRow = {
        id: Number(raw.id),
        presales_id: Number(raw.presales_id),
        stage,
        step_index: Number(raw.step_index),
        title: String(raw.title),
        description: String(raw.description),
        form_fields: JSON.parse(String(raw.form_fields || '[]')) as unknown[],
        form_data: JSON.parse(String(raw.form_data || '{}')) as Record<string, unknown>,
        is_done: Boolean(raw.is_done),
        done_at: String(raw.done_at || ''),
        notes: String(raw.notes || ''),
      };
      (tasks[stage] ||= []).push(task);
    }
    const progress: Record<string, { total: number; done: number }> = {};
    for (const stage of PRESALES_STAGES) {
      const list = tasks[stage] || [];
      progress[stage] = {
        total: list.length,
        done: list.filter((t) => t.is_done).length,
      };
    }
    const current = String(ps.stage || 'lead');
    const currentIdx = PRESALES_STAGES.indexOf(current as (typeof PRESALES_STAGES)[number]);
    const nextStage = currentIdx >= 0 && currentIdx < PRESALES_STAGES.length - 1
      ? PRESALES_STAGES[currentIdx + 1]
      : null;
    const curProg = progress[current] || { total: 0, done: 0 };
    const currentComplete = curProg.total === 0 || curProg.done >= curProg.total;
    let blockReason = '';
    let canAdvance = false;
    if (ps.status !== 'active') {
      blockReason = 'Pre-sales đã đóng hoặc đã chuyển lifecycle.';
    } else if (!nextStage) {
      blockReason = 'Đã ở giai đoạn Proposal — chờ ký HĐ để tạo Lifecycle.';
    } else if (!currentComplete) {
      blockReason = 'Hoàn thành tất cả task giai đoạn hiện tại trước khi chuyển bước.';
    } else if (nextStage === 'proposal' && current === 'consult') {
      const plan = this.getPreliminaryPlan(ps.id);
      const val = validatePreliminaryPlan(plan);
      if (!val.ok) blockReason = val.messages[0] || 'KH MKT sơ bộ chưa đủ';
      else canAdvance = true;
    } else {
      canAdvance = true;
    }
    return {
      presales: ps,
      tasks,
      progress,
      advance: {
        current_stage: current,
        next_stage: nextStage,
        can_advance_forward: canAdvance,
        block_reason: blockReason,
        current_complete: currentComplete,
        current_done: curProg.done,
        current_total: curProg.total,
        status: ps.status,
      },
    };
  }

  updatePresalesTask(taskId: number, body: PatchPresalesTaskBody, doneBy: number | null): void {
    const ts = this.ts();
    const sets = ['updated_at = ?'];
    const params: Array<string | number | bigint | Buffer | null> = [ts];
    if (body.is_done !== undefined) {
      sets.push('is_done = ?');
      params.push(body.is_done ? 1 : 0);
      sets.push('done_at = ?');
      params.push(body.is_done ? ts : '');
      if (doneBy != null) {
        sets.push('done_by = ?');
        params.push(doneBy);
      }
    }
    if (body.notes !== undefined) {
      sets.push('notes = ?');
      params.push(String(body.notes).slice(0, 4000));
    }
    if (body.form_data !== undefined) {
      sets.push('form_data = ?');
      params.push(JSON.stringify(body.form_data));
    }
    params.push(taskId);
    this.database
      .prepare(`UPDATE crm_lead_presales_tasks SET ${sets.join(', ')} WHERE id = ?`)
      .run(...params);
  }

  advancePresales(leadId: number): PresalesRow {
    this.assertNotInReviewQueue(leadId);
    const snap = this.getPresalesSnapshot(leadId);
    if (!snap) throw new Error('Không tìm thấy pre-sales');
    if (!snap.advance.can_advance_forward || !snap.advance.next_stage) {
      throw new Error(snap.advance.block_reason || 'Không thể chuyển giai đoạn');
    }
    const ts = this.ts();
    this.database
      .prepare(
        `UPDATE crm_lead_presales SET stage = ?, stage_entered_at = ?, updated_at = ? WHERE id = ?`,
      )
      .run(snap.advance.next_stage, ts, ts, snap.presales.id);
    return this.database
      .prepare('SELECT * FROM crm_lead_presales WHERE id = ?')
      .get(snap.presales.id) as unknown as PresalesRow;
  }

  getPreliminaryPlan(presalesId: number): Record<string, unknown> | null {
    const ps = this.database
      .prepare('SELECT draft_marketing_plan_id FROM crm_lead_presales WHERE id = ?')
      .get(presalesId) as { draft_marketing_plan_id: number | null } | undefined;
    if (!ps?.draft_marketing_plan_id) return null;
    return this.database
      .prepare('SELECT * FROM crm_marketing_plans WHERE id = ?')
      .get(ps.draft_marketing_plan_id) as Record<string, unknown> | null;
  }

  getOrCreatePreliminaryPlan(leadId: number, presalesId: number, serviceSlug: string): Record<string, unknown> {
    const existing = this.getPreliminaryPlan(presalesId);
    if (existing) return existing;
    const ts = this.ts();
    const name = `KH MKT sơ bộ — Lead #${leadId}${serviceSlug ? ` (${serviceSlug})` : ''}`;
    const result = this.database
      .prepare(
        `INSERT INTO crm_marketing_plans (
           code, name, status, plan_kind, lead_id, presales_id,
           north_star, objectives, strategy_framework_json, target_market_prof_json,
           target_market_steps4_json, created_at, updated_at
         ) VALUES (?, ?, 'draft', 'preliminary', ?, ?, '', '', ?, '{}', '{}', ?, ?)`,
      )
      .run(
        `PS-${presalesId}-DRAFT`,
        name.slice(0, 200),
        leadId,
        presalesId,
        JSON.stringify(defaultStrategyJson()),
        ts,
        ts,
      );
    const planId = Number(result.lastInsertRowid);
    this.database
      .prepare('UPDATE crm_lead_presales SET draft_marketing_plan_id = ?, updated_at = ? WHERE id = ?')
      .run(planId, ts, presalesId);
    return this.database.prepare('SELECT * FROM crm_marketing_plans WHERE id = ?').get(planId) as Record<
      string,
      unknown
    >;
  }

  patchMarketingPlan(leadId: number, body: PatchMarketingPlanBody): Record<string, unknown> {
    const snap = this.getPresalesSnapshot(leadId);
    if (!snap) throw new Error('Không tìm thấy pre-sales');
    const plan = this.getOrCreatePreliminaryPlan(leadId, snap.presales.id, snap.presales.service_slug);
    const planId = Number(plan.id);
    const ts = this.ts();
    const content = planContentFromRow(plan);
    const northStar = body.north_star !== undefined ? String(body.north_star) : String(plan.north_star || '');
    const objectives =
      body.objectives !== undefined ? String(body.objectives) : String(plan.objectives || '');
    if (body.name !== undefined) content.name = String(body.name);
    if (body.strategy_framework) {
      content.strategy_framework = { ...content.strategy_framework, ...body.strategy_framework };
    }
    this.database
      .prepare(
        `UPDATE crm_marketing_plans SET name = ?, north_star = ?, objectives = ?,
         strategy_framework_json = ?, updated_at = ? WHERE id = ?`,
      )
      .run(
        content.name.slice(0, 200),
        northStar,
        objectives,
        JSON.stringify(content.strategy_framework),
        ts,
        planId,
      );
    return this.database.prepare('SELECT * FROM crm_marketing_plans WHERE id = ?').get(planId) as Record<
      string,
      unknown
    >;
  }
}
