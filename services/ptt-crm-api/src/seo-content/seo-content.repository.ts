import { BadRequestException, Injectable, NotFoundException, OnModuleDestroy } from '@nestjs/common';
import { Pool, PoolClient } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import {
  APPROVAL_STAGES,
  APPROVE_NEXT_STATUS,
  CONTENT_WORKFLOW_STATUSES,
  PIPELINE_COLUMNS,
  SEO_CONTENT_SCHEMA,
  canTransition,
  opportunityScore,
} from './seo-content.constants';
import {
  SeoAeoChecklistResponse,
  SeoApprovalTimelineRow,
  SeoBriefPreviewResponse,
  SeoClusterRow,
  SeoContentRow,
  SeoContentVersionRow,
  SeoEntityGroupRow,
  SeoKeywordRow,
  SeoPageRow,
  SeoPipelineBoard,
  SeoQuestionRow,
  SeoSerpSnapshotRow,
} from './seo-content.types';

const SCHEMA = SEO_CONTENT_SCHEMA;

function tsUtc(): string {
  return new Date().toISOString().replace('T', ' ').slice(0, 19);
}

function parseJson(raw: unknown): Record<string, unknown> {
  if (raw == null) return {};
  if (typeof raw === 'object' && !Array.isArray(raw)) return raw as Record<string, unknown>;
  try {
    return JSON.parse(String(raw)) as Record<string, unknown>;
  } catch {
    return {};
  }
}

function governanceEnabled(): boolean {
  const flag = (process.env.PTT_SEO_GOVERNANCE_ENABLED ?? '1').trim().toLowerCase();
  return !['0', 'false', 'no', 'off'].includes(flag);
}

@Injectable()
export class SeoContentRepository implements OnModuleDestroy {
  private pool: Pool | null = null;

  constructor(private readonly config: AppConfigService) {}

  private get db(): Pool {
    if (!this.pool) {
      this.pool = new Pool({ connectionString: this.config.databaseUrl });
    }
    return this.pool;
  }

  onModuleDestroy(): void {
    void this.pool?.end();
    this.pool = null;
  }

  private mapContent(row: Record<string, unknown>): SeoContentRow {
    return {
      id: Number(row.id),
      customer_id: Number(row.customer_id),
      project_id: row.project_id != null ? Number(row.project_id) : null,
      lifecycle_id: row.lifecycle_id != null ? Number(row.lifecycle_id) : null,
      title: String(row.title ?? ''),
      slug: String(row.slug ?? ''),
      content_type: String(row.content_type ?? 'blog'),
      workflow_status: String(row.workflow_status ?? 'idea'),
      target_keyword_id: row.target_keyword_id != null ? Number(row.target_keyword_id) : null,
      target_question_id: row.target_question_id != null ? Number(row.target_question_id) : null,
      intent: String(row.intent ?? ''),
      funnel_stage: String(row.funnel_stage ?? ''),
      owner_staff_id: row.owner_staff_id != null ? Number(row.owner_staff_id) : null,
      due_date: row.due_date != null ? String(row.due_date) : null,
      publish_date: row.publish_date != null ? String(row.publish_date) : null,
      brief: parseJson(row.brief_json),
      outline: parseJson(row.outline_json),
      body_html: String(row.body_html ?? ''),
      seo_score: row.seo_score != null ? Number(row.seo_score) : null,
      aeo_score: row.aeo_score != null ? Number(row.aeo_score) : null,
      created_at: row.created_at != null ? String(row.created_at) : null,
      updated_at: row.updated_at != null ? String(row.updated_at) : null,
    };
  }

  async listKeywords(
    customerId: number,
    params?: { q?: string; intent?: string; clusterId?: number; limit?: number },
  ): Promise<SeoKeywordRow[]> {
    const limit = Math.min(params?.limit ?? 500, 1000);
    const values: unknown[] = [customerId];
    let sql = `SELECT k.*, c.name AS cluster_name
               FROM ${SCHEMA}.seo_keywords k
               LEFT JOIN ${SCHEMA}.seo_keyword_clusters c
                 ON c.id = k.cluster_id AND c.customer_id = k.customer_id AND c.status = 'active'
               WHERE k.customer_id = $1 AND k.status = 'active'`;
    if (params?.intent) {
      values.push(params.intent);
      sql += ` AND k.intent = $${values.length}`;
    }
    if (params?.clusterId != null) {
      values.push(params.clusterId);
      sql += ` AND k.cluster_id = $${values.length}`;
    }
    if (params?.q) {
      values.push(`%${params.q}%`);
      sql += ` AND k.phrase ILIKE $${values.length}`;
    }
    values.push(limit);
    sql += ` ORDER BY COALESCE(k.opportunity_score, 0) DESC, k.id DESC LIMIT $${values.length}`;
    const result = await this.db.query(sql, values);
    return result.rows.map((row) => ({
      id: Number(row.id),
      customer_id: Number(row.customer_id),
      phrase: String(row.phrase ?? ''),
      volume: row.volume != null ? Number(row.volume) : null,
      difficulty: row.difficulty != null ? Number(row.difficulty) : null,
      intent: String(row.intent ?? ''),
      business_value: String(row.business_value ?? 'medium'),
      cluster_id: row.cluster_id != null ? Number(row.cluster_id) : null,
      opportunity_score: row.opportunity_score != null ? Number(row.opportunity_score) : null,
      status: String(row.status ?? ''),
      created_at: row.created_at != null ? String(row.created_at) : null,
      cluster_name: row.cluster_name != null ? String(row.cluster_name) : null,
    }));
  }

  async createKeyword(customerId: number, payload: Record<string, unknown>): Promise<SeoKeywordRow> {
    const phrase = String(payload.phrase ?? '').trim();
    if (!phrase) throw new BadRequestException({ error: 'missing_phrase' });
    const volume = payload.volume != null ? Number(payload.volume) : null;
    const difficulty = payload.difficulty != null ? Number(payload.difficulty) : null;
    const businessValue = String(payload.business_value ?? 'medium');
    const score = opportunityScore(volume, difficulty, businessValue);
    const result = await this.db.query<{ id: string }>(
      `INSERT INTO ${SCHEMA}.seo_keywords
         (customer_id, phrase, volume, difficulty, intent, business_value, opportunity_score, status, created_at)
       VALUES ($1,$2,$3,$4,$5,$6,$7,'active',NOW())
       RETURNING id`,
      [
        customerId,
        phrase,
        volume,
        difficulty,
        String(payload.intent ?? 'informational'),
        businessValue,
        score,
      ],
    );
    const row = await this.getKeyword(Number(result.rows[0].id));
    if (!row) throw new BadRequestException({ error: 'create_failed' });
    return row;
  }

  async importKeywordsCsv(customerId: number, csvText: string): Promise<number> {
    const lines = csvText.trim().split(/\r?\n/);
    if (lines.length < 2) return 0;
    const headers = lines[0].split(',').map((h) => h.trim().toLowerCase());
    let count = 0;
    for (const line of lines.slice(1)) {
      if (!line.trim()) continue;
      const cols = line.split(',');
      const row: Record<string, string> = {};
      headers.forEach((h, i) => {
        row[h] = (cols[i] ?? '').trim();
      });
      const phrase = row.phrase || row.keyword;
      if (!phrase) continue;
      await this.createKeyword(customerId, {
        phrase,
        volume: row.volume ? Number(row.volume) : null,
        difficulty: row.difficulty ? Number(row.difficulty) : null,
        intent: row.intent || 'informational',
        business_value: row.business_value || 'medium',
      });
      count += 1;
    }
    return count;
  }

  async getKeyword(keywordId: number): Promise<SeoKeywordRow | null> {
    const result = await this.db.query(`SELECT * FROM ${SCHEMA}.seo_keywords WHERE id = $1`, [keywordId]);
    const row = result.rows[0];
    if (!row) return null;
    return {
      id: Number(row.id),
      customer_id: Number(row.customer_id),
      phrase: String(row.phrase ?? ''),
      volume: row.volume != null ? Number(row.volume) : null,
      difficulty: row.difficulty != null ? Number(row.difficulty) : null,
      intent: String(row.intent ?? ''),
      business_value: String(row.business_value ?? 'medium'),
      cluster_id: row.cluster_id != null ? Number(row.cluster_id) : null,
      opportunity_score: row.opportunity_score != null ? Number(row.opportunity_score) : null,
      status: String(row.status ?? ''),
      created_at: row.created_at != null ? String(row.created_at) : null,
    };
  }

  async listQuestions(
    customerId: number,
    params?: { q?: string; limit?: number },
  ): Promise<SeoQuestionRow[]> {
    const limit = Math.min(params?.limit ?? 500, 1000);
    const values: unknown[] = [customerId];
    let sql = `SELECT * FROM ${SCHEMA}.seo_questions WHERE customer_id = $1 AND status = 'active'`;
    if (params?.q) {
      values.push(`%${params.q}%`);
      sql += ` AND question_text ILIKE $${values.length}`;
    }
    values.push(limit);
    sql += ` ORDER BY id DESC LIMIT $${values.length}`;
    const result = await this.db.query(sql, values);
    return result.rows.map((row) => ({
      id: Number(row.id),
      customer_id: Number(row.customer_id),
      question_text: String(row.question_text ?? ''),
      intent: String(row.intent ?? ''),
      funnel_stage: String(row.funnel_stage ?? ''),
      source: String(row.source ?? ''),
      answer_score: row.answer_score != null ? Number(row.answer_score) : null,
      status: String(row.status ?? ''),
      brand_name: String(row.brand_name ?? ''),
      lifecycle_id: row.lifecycle_id != null ? Number(row.lifecycle_id) : null,
      notes: String(row.notes ?? ''),
      created_at: row.created_at != null ? String(row.created_at) : null,
    }));
  }

  async createQuestion(customerId: number, payload: Record<string, unknown>): Promise<SeoQuestionRow> {
    const text = String(payload.question_text ?? '').trim();
    if (!text) throw new BadRequestException({ error: 'missing_question_text' });
    const result = await this.db.query<{ id: string }>(
      `INSERT INTO ${SCHEMA}.seo_questions
         (customer_id, question_text, intent, funnel_stage, source, status, created_at)
       VALUES ($1,$2,$3,$4,$5,'active',NOW())
       RETURNING id`,
      [
        customerId,
        text,
        String(payload.intent ?? 'informational'),
        String(payload.funnel_stage ?? 'awareness'),
        String(payload.source ?? 'manual'),
      ],
    );
    const id = Number(result.rows[0].id);
    const rows = await this.listQuestions(customerId, { limit: 1 });
    const found = rows.find((r) => r.id === id);
    if (!found) {
      const q = await this.db.query(`SELECT * FROM ${SCHEMA}.seo_questions WHERE id = $1`, [id]);
      const row = q.rows[0];
      return {
        id,
        customer_id: customerId,
        question_text: String(row.question_text),
        intent: String(row.intent ?? ''),
        funnel_stage: String(row.funnel_stage ?? ''),
        source: String(row.source ?? ''),
        answer_score: null,
        status: 'active',
        brand_name: '',
        lifecycle_id: null,
        notes: '',
        created_at: null,
      };
    }
    return found;
  }

  async getQuestion(questionId: number): Promise<SeoQuestionRow | null> {
    const result = await this.db.query(`SELECT * FROM ${SCHEMA}.seo_questions WHERE id = $1`, [questionId]);
    const row = result.rows[0];
    if (!row) return null;
    return {
      id: Number(row.id),
      customer_id: Number(row.customer_id),
      question_text: String(row.question_text ?? ''),
      intent: String(row.intent ?? ''),
      funnel_stage: String(row.funnel_stage ?? ''),
      source: String(row.source ?? ''),
      answer_score: row.answer_score != null ? Number(row.answer_score) : null,
      status: String(row.status ?? ''),
      brand_name: String(row.brand_name ?? ''),
      lifecycle_id: row.lifecycle_id != null ? Number(row.lifecycle_id) : null,
      notes: String(row.notes ?? ''),
      created_at: row.created_at != null ? String(row.created_at) : null,
    };
  }

  async listEntityGroups(customerId: number): Promise<SeoEntityGroupRow[]> {
    const result = await this.db.query<{
      intent: string;
      keyword_count: string;
      avg_score: string;
      top_score: string;
    }>(
      `SELECT intent,
              COUNT(*) AS keyword_count,
              ROUND(AVG(COALESCE(opportunity_score, 0))::numeric, 1) AS avg_score,
              MAX(COALESCE(opportunity_score, 0)) AS top_score
       FROM ${SCHEMA}.seo_keywords
       WHERE customer_id = $1 AND status = 'active'
       GROUP BY intent
       ORDER BY keyword_count DESC, top_score DESC`,
      [customerId],
    );
    const groups: SeoEntityGroupRow[] = [];
    for (const row of result.rows) {
      const intent = String(row.intent || 'informational');
      const samples = await this.db.query<{ phrase: string; opportunity_score: number | null }>(
        `SELECT phrase, opportunity_score FROM ${SCHEMA}.seo_keywords
         WHERE customer_id = $1 AND status = 'active' AND intent = $2
         ORDER BY COALESCE(opportunity_score, 0) DESC LIMIT 5`,
        [customerId, intent],
      );
      groups.push({
        entity_key: intent,
        label: intent.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
        intent,
        keyword_count: Number(row.keyword_count ?? 0),
        avg_opportunity_score: Number(row.avg_score ?? 0),
        top_opportunity_score: Number(row.top_score ?? 0),
        sample_keywords: samples.rows.map((s) => ({
          phrase: String(s.phrase),
          opportunity_score: s.opportunity_score != null ? Number(s.opportunity_score) : null,
        })),
      });
    }
    return groups;
  }

  async listOpportunities(customerId: number, minScore = 40, limit = 100): Promise<SeoKeywordRow[]> {
    const result = await this.db.query(
      `SELECT * FROM ${SCHEMA}.seo_keywords
       WHERE customer_id = $1 AND status = 'active' AND COALESCE(opportunity_score, 0) >= $2
       ORDER BY opportunity_score DESC NULLS LAST, id DESC
       LIMIT $3`,
      [customerId, minScore, limit],
    );
    return result.rows.map((row) => ({
      id: Number(row.id),
      customer_id: Number(row.customer_id),
      phrase: String(row.phrase ?? ''),
      volume: row.volume != null ? Number(row.volume) : null,
      difficulty: row.difficulty != null ? Number(row.difficulty) : null,
      intent: String(row.intent ?? ''),
      business_value: String(row.business_value ?? 'medium'),
      cluster_id: row.cluster_id != null ? Number(row.cluster_id) : null,
      opportunity_score: row.opportunity_score != null ? Number(row.opportunity_score) : null,
      status: String(row.status ?? ''),
      created_at: row.created_at != null ? String(row.created_at) : null,
    }));
  }

  async listClusters(customerId: number): Promise<SeoClusterRow[]> {
    try {
      const result = await this.db.query(
        `SELECT c.*,
                (SELECT COUNT(*) FROM ${SCHEMA}.seo_keywords k
                 WHERE k.customer_id = c.customer_id AND k.cluster_id = c.id AND k.status = 'active') AS keyword_count
         FROM ${SCHEMA}.seo_keyword_clusters c
         WHERE c.customer_id = $1 AND c.status = 'active'
         ORDER BY c.name ASC, c.id ASC`,
        [customerId],
      );
      return result.rows.map((row) => ({
        id: Number(row.id),
        customer_id: Number(row.customer_id),
        name: String(row.name ?? ''),
        intent: String(row.intent ?? ''),
        notes: String(row.notes ?? ''),
        status: String(row.status ?? ''),
        keyword_count: Number(row.keyword_count ?? 0),
      }));
    } catch {
      return [];
    }
  }

  async createCluster(customerId: number, payload: Record<string, unknown>): Promise<SeoClusterRow> {
    const name = String(payload.name ?? '').trim();
    if (!name) throw new BadRequestException({ error: 'missing_cluster_name' });
    const result = await this.db.query<{ id: string }>(
      `INSERT INTO ${SCHEMA}.seo_keyword_clusters
         (customer_id, name, intent, notes, status, created_at, updated_at)
       VALUES ($1,$2,$3,$4,'active',NOW(),NOW())
       RETURNING id`,
      [customerId, name, String(payload.intent ?? 'informational'), String(payload.notes ?? '')],
    );
    const clusters = await this.listClusters(customerId);
    const found = clusters.find((c) => c.id === Number(result.rows[0].id));
    if (!found) throw new BadRequestException({ error: 'create_cluster_failed' });
    return found;
  }

  generateBriefTemplate(keyword?: SeoKeywordRow | null, question?: SeoQuestionRow | null): Record<string, unknown> {
    const primary = keyword?.phrase ?? question?.question_text ?? '';
    return {
      primary_topic: primary,
      objective: 'Tăng visibility organic và AEO coverage',
      target_audience: 'Người tìm kiếm có intent liên quan',
      sections: [
        'Answer-first intro',
        'Core content blocks',
        'FAQ / schema block',
        'Internal links',
        'CTA',
      ],
      checklist: [
        'Target keyword/question rõ ràng',
        'Heading theo câu hỏi',
        'Schema phù hợp',
        'AEO answer-first paragraph',
      ],
    };
  }

  async previewBrief(params: {
    customerId: number;
    keywordId?: number;
    questionId?: number;
  }): Promise<SeoBriefPreviewResponse> {
    let title = 'Untitled content';
    let keyword: SeoKeywordRow | null = null;
    let question: SeoQuestionRow | null = null;
    if (params.keywordId) {
      keyword = await this.getKeyword(params.keywordId);
      if (!keyword || keyword.customer_id !== params.customerId) {
        throw new BadRequestException({ error: 'keyword_not_found' });
      }
      title = `Content: ${keyword.phrase}`;
    } else if (params.questionId) {
      question = await this.getQuestion(params.questionId);
      if (!question || question.customer_id !== params.customerId) {
        throw new BadRequestException({ error: 'question_not_found' });
      }
      title = `FAQ: ${question.question_text.slice(0, 80)}`;
    } else {
      throw new BadRequestException({ error: 'missing_keyword_or_question' });
    }
    return {
      title,
      brief: this.generateBriefTemplate(keyword, question),
      source: 'template',
      keyword_id: params.keywordId ?? null,
      question_id: params.questionId ?? null,
      ai_available: Boolean((process.env.ANTHROPIC_API_KEY ?? '').trim()),
    };
  }

  async listContent(params: {
    customerId?: number;
    lifecycleId?: number;
    workflowStatus?: string;
    ownerStaffId?: number;
  }): Promise<SeoContentRow[]> {
    const values: unknown[] = [];
    let sql = `SELECT * FROM ${SCHEMA}.seo_content WHERE workflow_status != 'archived'`;
    if (params.customerId != null) {
      values.push(params.customerId);
      sql += ` AND customer_id = $${values.length}`;
    }
    if (params.lifecycleId != null) {
      values.push(params.lifecycleId);
      sql += ` AND lifecycle_id = $${values.length}`;
    }
    if (params.workflowStatus) {
      values.push(params.workflowStatus);
      sql += ` AND workflow_status = $${values.length}`;
    }
    if (params.ownerStaffId != null) {
      values.push(params.ownerStaffId);
      sql += ` AND owner_staff_id = $${values.length}`;
    }
    sql += ' ORDER BY updated_at DESC NULLS LAST, id DESC';
    const result = await this.db.query(sql, values);
    return result.rows.map((row) => this.mapContent(row));
  }

  async pipelineBoard(customerId?: number, lifecycleId?: number): Promise<SeoPipelineBoard> {
    const items = await this.listContent({ customerId, lifecycleId });
    const statusToCol = new Map<string, string>();
    for (const col of PIPELINE_COLUMNS) {
      for (const st of col.statuses) statusToCol.set(st, col.key);
    }
    const buckets = new Map<string, SeoContentRow[]>();
    for (const col of PIPELINE_COLUMNS) buckets.set(col.key, []);
    for (const item of items) {
      const key = statusToCol.get(item.workflow_status) ?? 'idea';
      buckets.get(key)?.push(item);
    }
    return {
      columns: PIPELINE_COLUMNS.map((col) => ({
        key: col.key,
        label: col.label,
        items: buckets.get(col.key) ?? [],
      })),
    };
  }

  async approvalTimeline(contentId: number): Promise<SeoApprovalTimelineRow[]> {
    const timeline: SeoApprovalTimelineRow[] = [];
    for (const stage of APPROVAL_STAGES) {
      const result = await this.db.query<{
        status: string;
        notes: string;
        actor_id: string;
        created_at: string | null;
      }>(
        `SELECT status, notes, actor_id, created_at
         FROM ${SCHEMA}.seo_content_approvals
         WHERE content_id = $1 AND stage = $2
         ORDER BY id DESC LIMIT 1`,
        [contentId, stage],
      );
      const row = result.rows[0];
      timeline.push({
        stage,
        status: row?.status ?? 'pending',
        notes: row?.notes ?? '',
        actor_id: row?.actor_id ?? '',
        created_at: row?.created_at ?? null,
      });
    }
    return timeline;
  }

  async getContentDetail(contentId: number): Promise<SeoContentRow | null> {
    const result = await this.db.query(`SELECT * FROM ${SCHEMA}.seo_content WHERE id = $1`, [contentId]);
    const row = result.rows[0];
    if (!row) return null;
    const content = this.mapContent(row);
    content.approvals = await this.approvalTimeline(contentId);
    if (content.target_keyword_id) {
      content.target_keyword = await this.getKeyword(content.target_keyword_id);
    }
    if (content.target_question_id) {
      content.target_question = await this.getQuestion(content.target_question_id);
    }
    return content;
  }

  async createContent(payload: Record<string, unknown>): Promise<SeoContentRow> {
    const title = String(payload.title ?? '').trim();
    if (!title) throw new BadRequestException({ error: 'missing_title' });
    const customerId = Number(payload.customer_id);
    const result = await this.db.query<{ id: string }>(
      `INSERT INTO ${SCHEMA}.seo_content (
         customer_id, project_id, lifecycle_id, title, slug, content_type, workflow_status,
         target_keyword_id, target_question_id, intent, funnel_stage, owner_staff_id, due_date,
         brief_json, outline_json, body_html, created_at, updated_at
       ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,NOW(),NOW())
       RETURNING id`,
      [
        customerId,
        payload.project_id ?? null,
        payload.lifecycle_id ?? null,
        title,
        String(payload.slug ?? ''),
        String(payload.content_type ?? 'blog'),
        String(payload.workflow_status ?? 'idea'),
        payload.target_keyword_id ?? null,
        payload.target_question_id ?? null,
        String(payload.intent ?? ''),
        String(payload.funnel_stage ?? ''),
        payload.owner_staff_id ?? null,
        payload.due_date ?? null,
        JSON.stringify(payload.brief ?? {}),
        JSON.stringify(payload.outline ?? {}),
        String(payload.body_html ?? ''),
      ],
    );
    const id = Number(result.rows[0].id);
    await this.logAudit(this.db, {
      customerId,
      entityType: 'content',
      entityId: id,
      action: 'create',
      actorId: String(payload.actor_id ?? ''),
    });
    const detail = await this.getContentDetail(id);
    if (!detail) throw new BadRequestException({ error: 'create_failed' });
    return detail;
  }

  async createContentFromResearch(params: {
    customerId: number;
    keywordId?: number;
    questionId?: number;
    lifecycleId?: number;
    projectId?: number;
    title?: string;
    brief?: Record<string, unknown>;
    ownerStaffId?: number;
    dueDate?: string;
    actorId?: string;
  }): Promise<SeoContentRow> {
    let title = String(params.title ?? '').trim();
    let intent = '';
    let keyword: SeoKeywordRow | null = null;
    let question: SeoQuestionRow | null = null;
    if (params.keywordId) {
      keyword = await this.getKeyword(params.keywordId);
      if (keyword) {
        if (!title) title = `Content: ${keyword.phrase}`;
        intent = keyword.intent;
      }
    } else if (params.questionId) {
      question = await this.getQuestion(params.questionId);
      if (question) {
        if (!title) title = `FAQ: ${question.question_text.slice(0, 80)}`;
        intent = question.intent;
      }
    }
    if (!title) title = 'Untitled content';
    const brief =
      params.brief && Object.keys(params.brief).length
        ? params.brief
        : this.generateBriefTemplate(keyword, question);
    return this.createContent({
      customer_id: params.customerId,
      lifecycle_id: params.lifecycleId,
      project_id: params.projectId,
      title,
      target_keyword_id: params.keywordId,
      target_question_id: params.questionId,
      intent,
      workflow_status: 'brief_ready',
      brief,
      owner_staff_id: params.ownerStaffId,
      due_date: params.dueDate,
      actor_id: params.actorId,
    });
  }

  async updateContent(contentId: number, payload: Record<string, unknown>): Promise<SeoContentRow> {
    const existing = await this.getContentDetail(contentId);
    if (!existing) throw new NotFoundException({ error: 'content_not_found' });
    const brief = payload.brief
      ? { ...existing.brief, ...(payload.brief as Record<string, unknown>) }
      : existing.brief;
    const outline = payload.outline
      ? { ...existing.outline, ...(payload.outline as Record<string, unknown>) }
      : existing.outline;
    await this.db.query(
      `UPDATE ${SCHEMA}.seo_content SET
         title = COALESCE($2, title),
         slug = COALESCE($3, slug),
         content_type = COALESCE($4, content_type),
         body_html = COALESCE($5, body_html),
         due_date = COALESCE($6, due_date),
         owner_staff_id = COALESCE($7, owner_staff_id),
         intent = COALESCE($8, intent),
         funnel_stage = COALESCE($9, funnel_stage),
         brief_json = $10,
         outline_json = $11,
         updated_at = NOW()
       WHERE id = $1`,
      [
        contentId,
        payload.title ?? null,
        payload.slug ?? null,
        payload.content_type ?? null,
        payload.body_html ?? null,
        payload.due_date ?? null,
        payload.owner_staff_id ?? null,
        payload.intent ?? null,
        payload.funnel_stage ?? null,
        JSON.stringify(brief),
        JSON.stringify(outline),
      ],
    );
    const detail = await this.getContentDetail(contentId);
    if (!detail) throw new NotFoundException({ error: 'content_not_found' });
    return detail;
  }

  async transitionStatus(
    contentId: number,
    targetStatus: string,
    actorId: string,
    notes: string,
  ): Promise<SeoContentRow> {
    if (!CONTENT_WORKFLOW_STATUSES.includes(targetStatus as (typeof CONTENT_WORKFLOW_STATUSES)[number])) {
      throw new BadRequestException({ error: 'invalid_status', status: targetStatus });
    }
    const existing = await this.getContentDetail(contentId);
    if (!existing) throw new NotFoundException({ error: 'content_not_found' });
    if (!canTransition(existing.workflow_status, targetStatus)) {
      throw new BadRequestException({
        error: 'invalid_transition',
        from: existing.workflow_status,
        to: targetStatus,
      });
    }
    if (targetStatus === 'published' && governanceEnabled()) {
      await this.assertPublishAllowed(existing);
    }
    await this.db.query(
      `UPDATE ${SCHEMA}.seo_content SET workflow_status = $2, updated_at = NOW() WHERE id = $1`,
      [contentId, targetStatus],
    );
    await this.logAudit(this.db, {
      customerId: existing.customer_id,
      entityType: 'content',
      entityId: contentId,
      action: `status:${existing.workflow_status}->${targetStatus}`,
      actorId,
      payload: { notes },
    });
    const detail = await this.getContentDetail(contentId);
    if (!detail) throw new NotFoundException({ error: 'content_not_found' });
    return detail;
  }

  async approveStage(params: {
    contentId: number;
    stage: string;
    approved: boolean;
    actorId: string;
    notes: string;
  }): Promise<SeoContentRow> {
    const existing = await this.getContentDetail(params.contentId);
    if (!existing) throw new NotFoundException({ error: 'content_not_found' });
    const client = await this.db.connect();
    try {
      await client.query('BEGIN');
      const status = params.approved ? 'approved' : 'rejected';
      await client.query(
        `INSERT INTO ${SCHEMA}.seo_content_approvals
           (content_id, stage, status, actor_id, notes, created_at)
         VALUES ($1,$2,$3,$4,$5,$6)`,
        [params.contentId, params.stage, status, params.actorId, params.notes, tsUtc()],
      );
      if (params.approved) {
        if (params.stage === 'client_review' && governanceEnabled()) {
          await this.assertPublishAllowed(existing, client);
        }
        const next = APPROVE_NEXT_STATUS[params.stage];
        if (next && canTransition(existing.workflow_status, next)) {
          await client.query(
            `UPDATE ${SCHEMA}.seo_content SET workflow_status = $2, updated_at = NOW() WHERE id = $1`,
            [params.contentId, next],
          );
        }
      } else if (canTransition(existing.workflow_status, 'in_writing')) {
        await client.query(
          `UPDATE ${SCHEMA}.seo_content SET workflow_status = 'in_writing', updated_at = NOW() WHERE id = $1`,
          [params.contentId],
        );
      }
      await this.logAudit(client, {
        customerId: existing.customer_id,
        entityType: 'content',
        entityId: params.contentId,
        action: `approval:${params.stage}:${status}`,
        actorId: params.actorId,
        payload: { notes: params.notes },
      });
      await client.query('COMMIT');
    } catch (err) {
      await client.query('ROLLBACK');
      throw err;
    } finally {
      client.release();
    }
    const detail = await this.getContentDetail(params.contentId);
    if (!detail) throw new NotFoundException({ error: 'content_not_found' });
    return detail;
  }

  async listVersions(contentId: number): Promise<SeoContentVersionRow[]> {
    const result = await this.db.query(
      `SELECT id, content_id, version_number, changes_summary, created_by, created_at,
              LENGTH(body_html) AS body_length
       FROM ${SCHEMA}.seo_content_versions
       WHERE content_id = $1
       ORDER BY version_number DESC`,
      [contentId],
    );
    return result.rows.map((row) => ({
      id: Number(row.id),
      content_id: Number(row.content_id),
      version_number: Number(row.version_number),
      changes_summary: String(row.changes_summary ?? ''),
      created_by: String(row.created_by ?? ''),
      created_at: row.created_at != null ? String(row.created_at) : null,
      body_length: row.body_length != null ? Number(row.body_length) : undefined,
    }));
  }

  async getVersion(contentId: number, versionId: number): Promise<SeoContentVersionRow | null> {
    const result = await this.db.query(
      `SELECT * FROM ${SCHEMA}.seo_content_versions WHERE id = $1 AND content_id = $2`,
      [versionId, contentId],
    );
    const row = result.rows[0];
    if (!row) return null;
    return {
      id: Number(row.id),
      content_id: Number(row.content_id),
      version_number: Number(row.version_number),
      body_html: String(row.body_html ?? ''),
      changes_summary: String(row.changes_summary ?? ''),
      created_by: String(row.created_by ?? ''),
      created_at: row.created_at != null ? String(row.created_at) : null,
    };
  }

  async saveVersion(params: {
    contentId: number;
    bodyHtml: string;
    changesSummary?: string;
    createdBy?: string;
  }): Promise<SeoContentVersionRow> {
    const verResult = await this.db.query<{ v: string }>(
      `SELECT COALESCE(MAX(version_number), 0) AS v FROM ${SCHEMA}.seo_content_versions WHERE content_id = $1`,
      [params.contentId],
    );
    const ver = Number(verResult.rows[0]?.v ?? 0) + 1;
    const result = await this.db.query<{ id: string }>(
      `INSERT INTO ${SCHEMA}.seo_content_versions
         (content_id, version_number, body_html, changes_summary, created_by, created_at)
       VALUES ($1,$2,$3,$4,$5,NOW())
       RETURNING id`,
      [
        params.contentId,
        ver,
        params.bodyHtml,
        params.changesSummary ?? '',
        params.createdBy ?? '',
      ],
    );
    await this.db.query(
      `UPDATE ${SCHEMA}.seo_content SET body_html = $2, updated_at = NOW() WHERE id = $1`,
      [params.contentId, params.bodyHtml],
    );
    const version = await this.getVersion(params.contentId, Number(result.rows[0].id));
    if (!version) throw new BadRequestException({ error: 'version_save_failed' });
    return version;
  }

  async aeoChecklist(contentId: number): Promise<SeoAeoChecklistResponse> {
    const item = await this.getContentDetail(contentId);
    if (!item) throw new NotFoundException({ error: 'content_not_found' });
    const brief = item.brief ?? {};
    const outline = item.outline ?? {};
    const checklistItems = Array.isArray(brief.checklist) ? (brief.checklist as string[]) : [];
    const body = (item.body_html ?? '').toLowerCase();
    const schemaRaw = outline.schema_json ?? outline.schema ?? '';
    const hasSchema = Boolean(String(schemaRaw).trim());
    const hasFaq = body.includes('faq') || body.includes('câu hỏi');
    const hasAnswerFirst = body.trim().length > 80;
    const rows: Array<{ label: string; done: boolean }> = [];
    for (const label of checklistItems) {
      const low = label.toLowerCase();
      let done = false;
      if (low.includes('schema')) done = hasSchema;
      else if (low.includes('aeo') || low.includes('answer')) done = hasAnswerFirst && hasFaq;
      else if (low.includes('keyword') || low.includes('question')) {
        done = Boolean(brief.primary_topic || item.target_keyword_id || item.target_question_id);
      } else if (low.includes('heading')) done = body.includes('<h');
      else done = body.length > 0;
      rows.push({ label, done });
    }
    if (!rows.length) {
      rows.push(
        { label: 'Answer-first paragraph', done: hasAnswerFirst },
        { label: 'FAQ block', done: hasFaq },
        { label: 'Schema JSON-LD', done: hasSchema },
        { label: 'Linked AEO question', done: item.target_question_id != null },
      );
    }
    const doneCount = rows.filter((r) => r.done).length;
    const total = rows.length;
    return {
      content_id: contentId,
      items: rows,
      done_count: doneCount,
      total,
      score_pct: total > 0 ? Math.round((1000 * doneCount) / total) / 10 : 0,
    };
  }

  private async assertPublishAllowed(content: SeoContentRow, client: Pool | PoolClient = this.db): Promise<void> {
    const brief = content.brief ?? {};
    const missing: string[] = [];
    if (!content.title.trim()) missing.push('title');
    if (!brief.primary_topic && !content.target_keyword_id) missing.push('target_keyword');
    if (missing.length) {
      throw new BadRequestException({
        error: 'governance_block',
        message: `Thiếu metadata: ${missing.join(', ')}`,
      });
    }
    const critical = await client.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.seo_technical_issues
       WHERE customer_id = $1 AND severity = 'critical'
         AND status NOT IN ('closed', 'verified')`,
      [content.customer_id],
    );
    if (Number(critical.rows[0]?.c ?? 0) > 0) {
      throw new BadRequestException({
        error: 'governance_block',
        message: 'Còn issue kỹ thuật critical mở',
      });
    }
  }

  async listSerpSnapshots(customerId: number, limit = 50): Promise<SeoSerpSnapshotRow[]> {
    const safeLimit = Math.max(1, Math.min(limit, 200));
    const result = await this.db.query(
      `SELECT id, customer_id, keyword_id, phrase, snapshot_date, results_json, source, created_at
       FROM ${SCHEMA}.seo_serp_snapshots
       WHERE customer_id = $1
       ORDER BY snapshot_date DESC, id DESC
       LIMIT $2`,
      [customerId, safeLimit],
    );
    return result.rows.map((row) => {
      let results: unknown[] = [];
      try {
        const parsed = JSON.parse(String(row.results_json ?? '[]'));
        results = Array.isArray(parsed) ? parsed : [];
      } catch {
        results = [];
      }
      return {
        id: Number(row.id),
        customer_id: Number(row.customer_id),
        keyword_id: row.keyword_id != null ? Number(row.keyword_id) : null,
        phrase: String(row.phrase ?? ''),
        snapshot_date: String(row.snapshot_date ?? ''),
        source: String(row.source ?? ''),
        created_at: String(row.created_at ?? ''),
        result_count: results.length,
        top_results: results.slice(0, 5).map((item) =>
          typeof item === 'object' && item != null ? (item as Record<string, unknown>) : { value: item },
        ),
      };
    });
  }

  async listPages(customerId: number, limit = 500): Promise<SeoPageRow[]> {
    const safeLimit = Math.max(1, Math.min(limit, 500));
    const result = await this.db.query(
      `SELECT id, customer_id, url, title, slug, content_type, schema_type, status, last_crawled_at, created_at
       FROM ${SCHEMA}.seo_pages
       WHERE customer_id = $1
       ORDER BY url ASC
       LIMIT $2`,
      [customerId, safeLimit],
    );
    return result.rows.map((row) => ({
      id: Number(row.id),
      customer_id: Number(row.customer_id),
      url: String(row.url ?? ''),
      title: String(row.title ?? ''),
      slug: String(row.slug ?? ''),
      content_type: String(row.content_type ?? ''),
      schema_type: String(row.schema_type ?? ''),
      status: String(row.status ?? ''),
      last_crawled_at: row.last_crawled_at != null ? String(row.last_crawled_at) : null,
      created_at: row.created_at != null ? String(row.created_at) : null,
    }));
  }

  private async logAudit(
    client: Pool | PoolClient,
    params: {
      customerId: number;
      entityType: string;
      entityId: number;
      action: string;
      actorId: string;
      payload?: Record<string, unknown>;
    },
  ): Promise<void> {
    await client.query(
      `INSERT INTO ${SCHEMA}.seo_audit_log
         (customer_id, entity_type, entity_id, action, actor_id, payload_json, created_at)
       VALUES ($1,$2,$3,$4,$5,$6,$7)`,
      [
        params.customerId,
        params.entityType,
        params.entityId,
        params.action,
        params.actorId,
        JSON.stringify(params.payload ?? {}),
        tsUtc(),
      ],
    );
  }
}
