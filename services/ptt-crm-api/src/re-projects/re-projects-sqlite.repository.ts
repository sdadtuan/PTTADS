import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { randomBytes } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import { catalogTs } from '../catalog/catalog-slug.util';
import { AppConfigService } from '../config/app-config.service';
import { computeKpiBoardStats, computeProductInventoryStats } from './re-projects-inventory.util';
import {
  currentPeriodMonth,
  KPI_CATEGORIES,
  KPI_METRIC_TEMPLATES,
  KPI_TRACK_STATUSES,
  mapReTrackToStaffStatus,
  mapStaffToReTrackStatus,
  parsePeriodMonth,
  RE_LEADS_NEW_EXCLUDED_STATUSES,
  RE_LEADS_NEW_METRIC_CODE,
} from './re-projects-kpi.util';
import {
  defaultBusinessPlan,
  defaultMarketingPlan,
  defaultSalesPlan,
  mergePlan,
  parseJsonPlan,
  slugTypeCode,
} from './re-projects-plan.util';
import { computeProjectWorkflow } from './re-projects-workflow.util';
import {
  BUDGET_CATEGORY_LABELS,
  BUDGET_CATEGORIES,
  CreateReProjectBody,
  DEFAULT_PROJECT_TYPE_LABELS,
  KPI_CATEGORY_LABELS,
  KPI_TRACK_STATUS_LABELS,
  PRICE_LIST_STATUS_LABELS,
  PRICE_LIST_STATUSES,
  PRODUCT_LINE_LABELS,
  PRODUCT_LINES,
  PRODUCT_STATUS_LABELS,
  PRODUCT_TYPOLOGIES,
  PRODUCT_TYPOLOGY_LABELS,
  PROJECT_STATUS_LABELS,
  PROJECT_STATUSES,
  PRODUCT_STATUSES,
  PROJECT_STAFF_ROLE_LABELS,
  PROJECT_STAFF_ROLES,
  RePriceListRow,
  ReProjectLeadConfigRow,
  ReProjectRow,
  ReProjectStaffRow,
  ReProjectTypeRow,
  RISK_CATEGORY_LABELS,
  RISK_LEVEL_LABELS,
  RISK_CATEGORIES,
  RISK_LEVELS,
  SavePriceListBody,
  SaveProductBody,
  SaveProjectLeadConfigBody,
  SaveProjectTypeBody,
  UpdateProjectStaffBody,
} from './re-projects.types';

@Injectable()
export class ReProjectsSqliteRepository implements OnModuleDestroy {
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

  private tableExists(name: string): boolean {
    const row = this.database
      .prepare("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?")
      .get(name);
    return row != null;
  }

  private seedProjectTypes(): void {
    if (!this.tableExists('crm_re_project_types')) return;
    const n = this.database.prepare('SELECT COUNT(*) AS c FROM crm_re_project_types').get() as
      | { c: number }
      | undefined;
    if (n && Number(n.c) > 0) return;
    const ts = catalogTs();
    let i = 0;
    for (const [code, name] of Object.entries(DEFAULT_PROJECT_TYPE_LABELS)) {
      i += 1;
      this.database
        .prepare(
          `INSERT INTO crm_re_project_types (code, name, description, sort_order, active, created_at, updated_at)
           VALUES (?, ?, ?, ?, 1, ?, ?)`,
        )
        .run(code, name, '', i * 10, ts, ts);
    }
  }

  private projectTypeLabelMap(includeInactive = false): Record<string, string> {
    const types = this.listProjectTypes(includeInactive);
    const out: Record<string, string> = {};
    for (const t of types) out[t.code] = t.name;
    return out;
  }

  private validateProjectType(code: string, allowInactive = false): string {
    const c = String(code ?? '').trim();
    if (!c) throw new Error('Thiếu loại BĐS.');
    if (!this.tableExists('crm_re_project_types')) throw new Error('Loại BĐS không tồn tại.');

    const lookup = (): { code: string; active: number } | undefined =>
      this.database
        .prepare('SELECT code, active FROM crm_re_project_types WHERE lower(code) = lower(?)')
        .get(c) as { code: string; active: number } | undefined;

    let row = lookup();
    if (!row) {
      const cnt = this.database.prepare('SELECT COUNT(*) AS c FROM crm_re_project_types').get() as
        | { c: number }
        | undefined;
      if (!cnt || Number(cnt.c) === 0) {
        this.seedProjectTypes();
        row = lookup();
      }
    }
    if (!row) throw new Error('Loại BĐS không tồn tại.');
    if (!allowInactive && !Number(row.active)) {
      throw new Error('Loại BĐS đang tắt — không thể gán cho dự án mới.');
    }
    return row.code;
  }

  private mapProjectRow(row: Record<string, unknown>, typeLabels: Record<string, string>): ReProjectRow {
    const bp = mergePlan(
      parseJsonPlan(String(row.business_plan_json ?? ''), defaultBusinessPlan()),
      defaultBusinessPlan(),
    );
    const mp = mergePlan(
      parseJsonPlan(String(row.marketing_plan_json ?? ''), defaultMarketingPlan()),
      defaultMarketingPlan(),
    );
    const sp = mergePlan(
      parseJsonPlan(String(row.sales_plan_json ?? ''), defaultSalesPlan()),
      defaultSalesPlan(),
    );
    const pt = String(row.project_type ?? 'can_ho');
    const st = String(row.status ?? 'planning');
    const total = Number(row.total_units ?? 0);
    const sold = Number(row.sold_units ?? 0);
    return {
      id: Number(row.id),
      code: String(row.code ?? ''),
      name: String(row.name ?? ''),
      project_type: pt,
      project_type_label: typeLabels[pt] ?? DEFAULT_PROJECT_TYPE_LABELS[pt] ?? pt,
      status: st,
      status_label: PROJECT_STATUS_LABELS[st] ?? st,
      location_address: String(row.location_address ?? ''),
      district: String(row.district ?? ''),
      city: String(row.city ?? ''),
      developer_name: String(row.developer_name ?? ''),
      investor_name: String(row.investor_name ?? ''),
      total_land_area_m2: row.total_land_area_m2 != null ? Number(row.total_land_area_m2) : null,
      total_units: total,
      sold_units: sold,
      sell_through_pct: total > 0 ? Math.round((sold / total) * 1000) / 10 : 0,
      revenue_target_vnd: Number(row.revenue_target_vnd ?? 0),
      start_date: String(row.start_date ?? ''),
      presale_date: String(row.presale_date ?? ''),
      handover_date: String(row.handover_date ?? ''),
      description: String(row.description ?? ''),
      notes: String(row.notes ?? ''),
      business_plan: bp,
      marketing_plan: mp,
      sales_plan: sp,
      created_at: String(row.created_at ?? ''),
      updated_at: String(row.updated_at ?? ''),
    };
  }

  private staffLookup(staffIds: Set<number>): Record<number, Record<string, unknown>> {
    const ids = [...staffIds].filter((i) => i > 0).sort((a, b) => a - b);
    if (!ids.length) return {};
    const placeholders = ids.map(() => '?').join(',');
    try {
      const rows = this.database
        .prepare(`SELECT id, name, job_title, department FROM crm_staff WHERE id IN (${placeholders})`)
        .all(...ids) as Array<Record<string, unknown>>;
      const out: Record<number, Record<string, unknown>> = {};
      for (const r of rows) out[Number(r.id)] = r;
      return out;
    } catch {
      const rows = this.database
        .prepare(`SELECT id, name FROM crm_staff WHERE id IN (${placeholders})`)
        .all(...ids) as Array<Record<string, unknown>>;
      const out: Record<number, Record<string, unknown>> = {};
      for (const r of rows) {
        out[Number(r.id)] = { name: r.name, job_title: '', department: '' };
      }
      return out;
    }
  }

  private enrichProductRow(d: Record<string, unknown>, staffMap: Record<number, Record<string, unknown>>): void {
    const line = String(d.product_line ?? '');
    const typo = String(d.typology ?? '');
    d.product_line_label = PRODUCT_LINE_LABELS[line] ?? (line || '—');
    d.typology_label = PRODUCT_TYPOLOGY_LABELS[typo] ?? (typo || '—');
    const sid = Number(d.sales_staff_id ?? 0);
    if (staffMap[sid]) {
      const st = staffMap[sid];
      d.sales_staff_name = st.name ?? '';
      d.sales_staff_title = st.job_title ?? '';
    } else {
      d.sales_staff_name = '';
      d.sales_staff_title = '';
    }
  }

  listProjectTypes(includeInactive = false): ReProjectTypeRow[] {
    if (!this.tableExists('crm_re_project_types')) return [];
    this.seedProjectTypes();
    const where = includeInactive ? '' : ' WHERE active = 1';
    const rows = this.database
      .prepare(
        `SELECT * FROM crm_re_project_types${where} ORDER BY sort_order ASC, name COLLATE NOCASE ASC, id ASC`,
      )
      .all() as Array<Record<string, unknown>>;
    return rows.map((r) => {
      const usage = this.database
        .prepare('SELECT COUNT(*) AS c FROM crm_re_projects WHERE lower(project_type) = lower(?)')
        .get(String(r.code ?? '')) as { c: number } | undefined;
      return {
        id: Number(r.id),
        code: String(r.code ?? ''),
        name: String(r.name ?? ''),
        description: String(r.description ?? ''),
        sort_order: Number(r.sort_order ?? 0),
        active: Boolean(Number(r.active ?? 0)),
        project_count: Number(usage?.c ?? 0),
        created_at: String(r.created_at ?? ''),
        updated_at: String(r.updated_at ?? ''),
      };
    });
  }

  saveProjectType(payload: SaveProjectTypeBody, typeId?: number): ReProjectTypeRow {
    if (!this.tableExists('crm_re_project_types')) throw new Error('Bảng loại BĐS chưa sẵn sàng.');
    const ts = catalogTs();
    const name = String(payload.name ?? '').trim();
    if (!name) throw new Error('Thiếu tên loại BĐS.');
    const description = String(payload.description ?? '').slice(0, 2000);
    const sortOrder = Number(payload.sort_order ?? 0);

    const isTruthy = (v: unknown) => v === true || v === 1 || v === '1' || v === 'true' || v === 'yes';

    let rid: number;
    if (typeId) {
      const prev = this.database
        .prepare('SELECT * FROM crm_re_project_types WHERE id = ?')
        .get(typeId) as Record<string, unknown> | undefined;
      if (!prev) throw new Error('Không tìm thấy loại BĐS.');
      const active =
        'active' in payload ? (isTruthy(payload.active) ? 1 : 0) : Number(prev.active ?? 0);
      let code = String(prev.code);
      const newCode = slugTypeCode(String(payload.code ?? code));
      if (newCode !== code) {
        const dup = this.database
          .prepare('SELECT id FROM crm_re_project_types WHERE lower(code)=lower(?) AND id<>?')
          .get(newCode, typeId);
        if (dup) throw new Error('Mã loại BĐS đã tồn tại.');
        const used = this.database
          .prepare('SELECT COUNT(*) AS c FROM crm_re_projects WHERE lower(project_type)=lower(?)')
          .get(code) as { c: number } | undefined;
        if (used && Number(used.c) > 0) {
          throw new Error('Không đổi mã khi đã có dự án đang dùng loại này.');
        }
        code = newCode;
      }
      this.database
        .prepare(
          `UPDATE crm_re_project_types SET code=?, name=?, description=?, sort_order=?, active=?, updated_at=? WHERE id=?`,
        )
        .run(code.slice(0, 40), name.slice(0, 120), description, sortOrder, active, ts, typeId);
      rid = typeId;
    } else {
      const code = slugTypeCode(String(payload.code ?? name));
      if (!code) throw new Error('Mã loại BĐS không hợp lệ.');
      const dup = this.database
        .prepare('SELECT id FROM crm_re_project_types WHERE lower(code)=lower(?)')
        .get(code);
      if (dup) throw new Error('Mã loại BĐS đã tồn tại.');
      const active = isTruthy(payload.active ?? true) ? 1 : 0;
      const result = this.database
        .prepare(
          `INSERT INTO crm_re_project_types (code, name, description, sort_order, active, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)`,
        )
        .run(code.slice(0, 40), name.slice(0, 120), description, sortOrder, active, ts, ts);
      rid = Number(result.lastInsertRowid);
    }
    const row = this.listProjectTypes(true).find((t) => t.id === rid);
    if (!row) throw new Error('Không tìm thấy loại BĐS sau khi lưu.');
    return row;
  }

  deleteProjectType(typeId: number): void {
    if (!this.tableExists('crm_re_project_types')) throw new Error('Không tìm thấy loại BĐS.');
    const row = this.database
      .prepare('SELECT code FROM crm_re_project_types WHERE id = ?')
      .get(typeId) as { code: string } | undefined;
    if (!row) throw new Error('Không tìm thấy loại BĐS.');
    const code = String(row.code);
    const used = this.database
      .prepare('SELECT COUNT(*) AS c FROM crm_re_projects WHERE lower(project_type)=lower(?)')
      .get(code) as { c: number } | undefined;
    if (used && Number(used.c) > 0) {
      throw new Error(`Không xóa được — còn ${Number(used.c)} dự án đang dùng loại «${code}».`);
    }
    this.database.prepare('DELETE FROM crm_re_project_types WHERE id = ?').run(typeId);
  }

  listProjects(q = ''): ReProjectRow[] {
    if (!this.tableExists('crm_re_projects')) return [];
    const labels = this.projectTypeLabelMap(true);
    const params: string[] = [];
    let where = '';
    if (q.trim()) {
      const like = `%${q.trim()}%`;
      where = ' WHERE name LIKE ? OR code LIKE ? OR district LIKE ? OR city LIKE ?';
      params.push(like, like, like, like);
    }
    const rows = this.database
      .prepare(`SELECT * FROM crm_re_projects${where} ORDER BY updated_at DESC, id DESC`)
      .all(...params) as Array<Record<string, unknown>>;
    return rows.map((r) => this.mapProjectRow(r, labels));
  }

  fetchProject(projectId: number): ReProjectRow | null {
    if (!this.tableExists('crm_re_projects')) return null;
    const labels = this.projectTypeLabelMap(true);
    const row = this.database
      .prepare('SELECT * FROM crm_re_projects WHERE id = ?')
      .get(projectId) as Record<string, unknown> | undefined;
    return row ? this.mapProjectRow(row, labels) : null;
  }

  createProject(payload: CreateReProjectBody): ReProjectRow {
    if (!this.tableExists('crm_re_projects')) throw new Error('Bảng dự án chưa sẵn sàng.');
    const name = String(payload.name ?? '').trim();
    if (!name) throw new Error('Thiếu tên dự án.');
    const ts = catalogTs();
    const pt = this.validateProjectType(String(payload.project_type ?? 'can_ho'));
    let st = String(payload.status ?? 'planning');
    if (!(PROJECT_STATUSES as readonly string[]).includes(st)) st = 'planning';

    const result = this.database
      .prepare(
        `INSERT INTO crm_re_projects (
           code, name, project_type, status, location_address, district, city,
           developer_name, investor_name, total_land_area_m2, total_units, sold_units,
           revenue_target_vnd, start_date, presale_date, handover_date,
           description, notes, business_plan_json, marketing_plan_json, sales_plan_json,
           created_at, updated_at
         ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        String(payload.code ?? '').slice(0, 40),
        name.slice(0, 240),
        pt,
        st,
        String(payload.location_address ?? '').slice(0, 500),
        String(payload.district ?? '').slice(0, 120),
        String(payload.city ?? '').slice(0, 120),
        String(payload.developer_name ?? '').slice(0, 240),
        String(payload.investor_name ?? '').slice(0, 240),
        payload.total_land_area_m2 ?? null,
        Number(payload.total_units ?? 0),
        Number(payload.sold_units ?? 0),
        Number(payload.revenue_target_vnd ?? 0),
        String(payload.start_date ?? '').slice(0, 10),
        String(payload.presale_date ?? '').slice(0, 10),
        String(payload.handover_date ?? '').slice(0, 10),
        String(payload.description ?? '').slice(0, 4000),
        String(payload.notes ?? '').slice(0, 4000),
        JSON.stringify(payload.business_plan ?? defaultBusinessPlan()),
        JSON.stringify(payload.marketing_plan ?? defaultMarketingPlan()),
        JSON.stringify(payload.sales_plan ?? defaultSalesPlan()),
        ts,
        ts,
      );
    const proj = this.fetchProject(Number(result.lastInsertRowid));
    if (!proj) throw new Error('Không tạo được dự án.');
    return proj;
  }

  updateProject(projectId: number, payload: CreateReProjectBody): ReProjectRow {
    const prev = this.fetchProject(projectId);
    if (!prev) throw new Error('Không tìm thấy dự án.');
    const ts = catalogTs();
    const merged = { ...prev, ...payload } as Record<string, unknown>;
    const pt =
      'project_type' in payload
        ? this.validateProjectType(String(payload.project_type ?? prev.project_type), true)
        : prev.project_type;
    let st = String(merged.status ?? prev.status);
    if (!(PROJECT_STATUSES as readonly string[]).includes(st)) st = prev.status;
    const bp = 'business_plan' in payload ? payload.business_plan : prev.business_plan;
    const mp = 'marketing_plan' in payload ? payload.marketing_plan : prev.marketing_plan;
    const sp = 'sales_plan' in payload ? payload.sales_plan : prev.sales_plan;

    this.database
      .prepare(
        `UPDATE crm_re_projects SET
           code=?, name=?, project_type=?, status=?,
           location_address=?, district=?, city=?,
           developer_name=?, investor_name=?, total_land_area_m2=?,
           total_units=?, sold_units=?, revenue_target_vnd=?,
           start_date=?, presale_date=?, handover_date=?,
           description=?, notes=?,
           business_plan_json=?, marketing_plan_json=?, sales_plan_json=?,
           updated_at=?
         WHERE id=?`,
      )
      .run(
        String(merged.code ?? '').slice(0, 40),
        String(merged.name ?? '').slice(0, 240),
        pt,
        st,
        String(merged.location_address ?? '').slice(0, 500),
        String(merged.district ?? '').slice(0, 120),
        String(merged.city ?? '').slice(0, 120),
        String(merged.developer_name ?? '').slice(0, 240),
        String(merged.investor_name ?? '').slice(0, 240),
        merged.total_land_area_m2 != null ? Number(merged.total_land_area_m2) : null,
        Number(merged.total_units ?? 0),
        Number(merged.sold_units ?? 0),
        Number(merged.revenue_target_vnd ?? 0),
        String(merged.start_date ?? '').slice(0, 10),
        String(merged.presale_date ?? '').slice(0, 10),
        String(merged.handover_date ?? '').slice(0, 10),
        String(merged.description ?? '').slice(0, 4000),
        String(merged.notes ?? '').slice(0, 4000),
        JSON.stringify(bp ?? defaultBusinessPlan()),
        JSON.stringify(mp ?? defaultMarketingPlan()),
        JSON.stringify(sp ?? defaultSalesPlan()),
        ts,
        projectId,
      );
    const out = this.fetchProject(projectId);
    if (!out) throw new Error('Không tìm thấy dự án.');
    return out;
  }

  deleteProject(projectId: number): void {
    if (!this.tableExists('crm_re_projects')) return;
    this.database.prepare('DELETE FROM crm_re_projects WHERE id = ?').run(projectId);
  }

  listProducts(projectId: number): Array<Record<string, unknown>> {
    if (!this.tableExists('crm_re_project_products')) return [];
    const rows = this.database
      .prepare(
        'SELECT * FROM crm_re_project_products WHERE project_id = ? ORDER BY zone, product_line, tower, unit_code',
      )
      .all(projectId) as Array<Record<string, unknown>>;
    const staffIds = new Set<number>();
    for (const r of rows) {
      if (r.sales_staff_id) staffIds.add(Number(r.sales_staff_id));
    }
    const staffMap = this.staffLookup(staffIds);
    return rows.map((r) => {
      const d = { ...r } as Record<string, unknown>;
      const st = String(d.status ?? 'available');
      d.status_label = PRODUCT_STATUS_LABELS[st] ?? st;
      this.enrichProductRow(d, staffMap);
      return d;
    });
  }

  saveProduct(projectId: number, payload: SaveProductBody, productId?: number): Record<string, unknown> {
    if (!this.tableExists('crm_re_project_products')) throw new Error('Bảng sản phẩm chưa sẵn sàng.');
    const ts = catalogTs();
    let st = String(payload.status ?? 'available');
    if (!(PRODUCT_STATUSES as readonly string[]).includes(st)) st = 'available';
    let line = String(payload.product_line ?? '');
    if (line && !(PRODUCT_LINES as readonly string[]).includes(line)) line = 'other';
    let typo = String(payload.typology ?? '');
    if (typo && !(PRODUCT_TYPOLOGIES as readonly string[]).includes(typo)) typo = 'other';
    let salesStaffId: number | null = payload.sales_staff_id != null ? Number(payload.sales_staff_id) : null;
    if (salesStaffId != null && salesStaffId <= 0) salesStaffId = null;
    const isCorner =
      payload.is_corner === true ||
      payload.is_corner === 1 ||
      payload.is_corner === '1' ||
      payload.is_corner === 'true' ||
      payload.is_corner === 'on'
        ? 1
        : 0;

    const fields = [
      String(payload.unit_code ?? '').slice(0, 40),
      String(payload.tower ?? '').slice(0, 40),
      String(payload.floor ?? '').slice(0, 20),
      line.slice(0, 40),
      String(payload.zone ?? '').slice(0, 60),
      typo.slice(0, 40),
      isCorner,
      salesStaffId,
      String(payload.product_type ?? '').slice(0, 80),
      payload.area_m2 ?? null,
      payload.bedrooms ?? null,
      String(payload.direction ?? '').slice(0, 40),
      String(payload.view_type ?? '').slice(0, 80),
      Number(payload.list_price_vnd ?? 0),
      Number(payload.net_price_vnd ?? 0),
      st,
      String(payload.notes ?? '').slice(0, 2000),
      String(payload.price_batch ?? '').slice(0, 80),
      ts,
    ];

    let rid: number;
    if (productId) {
      this.database
        .prepare(
          `UPDATE crm_re_project_products SET
             unit_code=?, tower=?, floor=?, product_line=?, zone=?, typology=?, is_corner=?,
             sales_staff_id=?, product_type=?, area_m2=?, bedrooms=?,
             direction=?, view_type=?, list_price_vnd=?, net_price_vnd=?, status=?, notes=?, price_batch=?, updated_at=?
           WHERE id=? AND project_id=?`,
        )
        .run(...fields, productId, projectId);
      rid = productId;
    } else {
      const result = this.database
        .prepare(
          `INSERT INTO crm_re_project_products (
             project_id, unit_code, tower, floor, product_line, zone, typology, is_corner,
             sales_staff_id, product_type, area_m2, bedrooms,
             direction, view_type, list_price_vnd, net_price_vnd, status, notes, price_batch, created_at, updated_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        )
        .run(projectId, ...fields.slice(0, -1), ts, fields[fields.length - 1]);
      rid = Number(result.lastInsertRowid);
    }
    const row = this.database.prepare('SELECT * FROM crm_re_project_products WHERE id = ?').get(rid) as
      | Record<string, unknown>
      | undefined;
    if (!row) throw new Error('Không lưu được sản phẩm.');
    const d = { ...row } as Record<string, unknown>;
    d.status_label = PRODUCT_STATUS_LABELS[String(d.status ?? '')] ?? '';
    const staffMap = this.staffLookup(new Set([Number(d.sales_staff_id ?? 0)]));
    this.enrichProductRow(d, staffMap);
    return d;
  }

  deleteProduct(projectId: number, productId: number): void {
    if (!this.tableExists('crm_re_project_products')) return;
    this.database
      .prepare('DELETE FROM crm_re_project_products WHERE id = ? AND project_id = ?')
      .run(productId, projectId);
  }

  private enrichKpiRow(d: Record<string, unknown>, staffMap: Record<number, Record<string, unknown>>): void {
    const cat = String(d.category ?? '');
    d.category_label = KPI_CATEGORY_LABELS[cat] ?? cat;
    const tgt = Number(d.target_value ?? 0);
    const act = Number(d.actual_value ?? 0);
    d.achievement_pct = tgt > 0 ? Math.round((act / tgt) * 1000) / 10 : 0;
    let tr = String(d.track_status ?? 'active');
    if (!(KPI_TRACK_STATUSES as readonly string[]).includes(tr)) tr = 'active';
    d.track_status = tr;
    d.track_status_label = KPI_TRACK_STATUS_LABELS[tr] ?? tr;
    const sid = Number(d.owner_staff_id ?? 0);
    if (sid && staffMap[sid]) {
      const st = staffMap[sid];
      d.owner_display = String(st.name ?? d.owner_name ?? '');
      d.owner_job_title = String(st.job_title ?? '');
      d.owner_department = String(st.department ?? '');
    } else {
      d.owner_display = String(d.owner_name ?? '');
      d.owner_job_title = '';
      d.owner_department = '';
    }
    const skId = Number(d.staff_kpi_id ?? 0);
    d.synced_to_staff = skId > 0;
    if (skId > 0) {
      try {
        const sk = this.database
          .prepare('SELECT actual_value, status FROM crm_staff_kpi WHERE id = ?')
          .get(skId) as { actual_value: number | null; status: string } | undefined;
        if (sk) {
          d.staff_kpi_status = String(sk.status ?? '');
          if (sk.actual_value != null) d.staff_kpi_actual = Number(sk.actual_value);
        }
      } catch {
        /* crm_staff_kpi may be absent in test DB */
      }
    }
  }

  private resolveOwnerStaff(payload: Record<string, unknown>): { staffId: number | null; ownerName: string } {
    let staffId: number | null = null;
    const rawId = payload.owner_staff_id;
    if (rawId != null && String(rawId).trim() !== '') {
      const parsed = Number(rawId);
      staffId = Number.isFinite(parsed) ? parsed : null;
    }
    let ownerName = String(payload.owner_name ?? '').trim();
    if (staffId && staffId > 0) {
      try {
        const row = this.database.prepare('SELECT name FROM crm_staff WHERE id = ?').get(staffId) as
          | { name: string }
          | undefined;
        if (row) ownerName = String(row.name || ownerName);
      } catch {
        /* ignore */
      }
    }
    return { staffId: staffId && staffId > 0 ? staffId : null, ownerName: ownerName.slice(0, 120) };
  }

  private resolveCrmMetric(
    payload: Record<string, unknown>,
    metricName: string,
    unit: string,
  ): { metricId: number | null; metricCode: string; name: string; unit: string } {
    let metricId: number | null = null;
    const rawMid = payload.metric_id;
    if (rawMid != null && String(rawMid).trim() !== '') {
      const parsed = Number(rawMid);
      metricId = Number.isFinite(parsed) ? parsed : null;
    }
    const metricCode = String(payload.metric_code ?? '').trim();
    const resolvedName = metricName;
    const resolvedUnit = unit;
    if (!this.tableExists('crm_kpi_metrics')) {
      return { metricId: null, metricCode: metricCode.slice(0, 40), name: resolvedName, unit: resolvedUnit };
    }
    try {
      if (metricId && metricId > 0) {
        const row = this.database
          .prepare('SELECT id, code, name, unit FROM crm_kpi_metrics WHERE id = ? AND active = 1')
          .get(metricId) as { id: number; code: string; name: string; unit: string } | undefined;
        if (row) {
          return {
            metricId: Number(row.id),
            metricCode: String(row.code),
            name: String(row.name),
            unit: String(row.unit || unit),
          };
        }
      }
      const codesToTry: string[] = [];
      if (metricCode) {
        codesToTry.push(metricCode, metricCode.toUpperCase(), `RE_${metricCode.toUpperCase()}`);
      }
      for (const tpl of KPI_METRIC_TEMPLATES) {
        if (metricCode && tpl.code === metricCode) codesToTry.push(tpl.crm_code);
        if (metricName && tpl.metric_name === metricName) codesToTry.push(tpl.crm_code);
      }
      for (const codeTry of codesToTry) {
        if (!codeTry) continue;
        const row = this.database
          .prepare(
            `SELECT id, code, name, unit FROM crm_kpi_metrics
             WHERE lower(trim(code)) = lower(?) AND active = 1`,
          )
          .get(codeTry) as { id: number; code: string; name: string; unit: string } | undefined;
        if (row) {
          return {
            metricId: Number(row.id),
            metricCode: String(row.code),
            name: String(row.name),
            unit: String(row.unit || unit),
          };
        }
      }
    } catch {
      /* ignore lookup errors */
    }
    return { metricId: null, metricCode: metricCode.slice(0, 40), name: resolvedName, unit: resolvedUnit };
  }

  private syncKpiToStaffModule(kpiId: number, projectId: number, ts?: string): boolean {
    if (!this.tableExists('crm_re_project_kpis') || !this.tableExists('crm_staff_kpi')) return false;
    const row = this.database
      .prepare('SELECT * FROM crm_re_project_kpis WHERE id = ? AND project_id = ?')
      .get(kpiId, projectId) as Record<string, unknown> | undefined;
    if (!row) return false;
    let staffId = Number(row.owner_staff_id ?? 0);
    let metricId = Number(row.metric_id ?? 0);
    if (!metricId) {
      const resolved = this.resolveCrmMetric(
        row,
        String(row.metric_name ?? ''),
        String(row.unit ?? ''),
      );
      metricId = Number(resolved.metricId ?? 0);
      if (metricId) {
        this.database
          .prepare('UPDATE crm_re_project_kpis SET metric_id=?, metric_code=? WHERE id=?')
          .run(metricId, resolved.metricCode, kpiId);
      }
    }
    if (staffId <= 0 || metricId <= 0) return false;
    const { year, month } = parsePeriodMonth(String(row.period_month ?? ''));
    if (year == null || month == null) return false;
    const proj = this.fetchProject(projectId);
    const projName = String(proj?.name ?? '');
    const note = String(row.notes ?? '').trim();
    const syncNote = `[Dự án BĐS: ${projName} (#${projectId})] ${note}`.trim().slice(0, 2000);
    const staffStatus = mapReTrackToStaffStatus(String(row.track_status ?? 'active'));
    const tsVal = ts ?? catalogTs();
    const tsD = new Date().toISOString().slice(0, 10);
    try {
      this.database
        .prepare(
          `INSERT INTO crm_staff_kpi (
             staff_id, metric_id, year, month,
             target_value, actual_value, status, note, created_at, updated_at
           )
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(staff_id, metric_id, year, month) DO UPDATE SET
             target_value = excluded.target_value,
             actual_value = excluded.actual_value,
             status = excluded.status,
             note = excluded.note,
             updated_at = excluded.updated_at`,
        )
        .run(
          staffId,
          metricId,
          year,
          month,
          Number(row.target_value ?? 0),
          Number(row.actual_value ?? 0),
          staffStatus,
          syncNote,
          tsD,
          tsVal,
        );
      const sk = this.database
        .prepare(
          'SELECT id FROM crm_staff_kpi WHERE staff_id = ? AND metric_id = ? AND year = ? AND month = ?',
        )
        .get(staffId, metricId, year, month) as { id: number } | undefined;
      if (sk) {
        this.database
          .prepare(
            'UPDATE crm_re_project_kpis SET staff_kpi_id = ?, metric_id = ?, updated_at = ? WHERE id = ?',
          )
          .run(Number(sk.id), metricId, tsVal, kpiId);
      }
    } catch {
      return false;
    }
    return true;
  }

  listKpis(projectId: number): Array<Record<string, unknown>> {
    if (!this.tableExists('crm_re_project_kpis')) return [];
    const rows = this.database
      .prepare(
        'SELECT * FROM crm_re_project_kpis WHERE project_id = ? ORDER BY period_month DESC, owner_staff_id, id',
      )
      .all(projectId) as Array<Record<string, unknown>>;
    const staffIds = new Set<number>();
    for (const r of rows) {
      if (r.owner_staff_id) staffIds.add(Number(r.owner_staff_id));
    }
    const staffMap = this.staffLookup(staffIds);
    return rows.map((r) => {
      const d = { ...r } as Record<string, unknown>;
      this.enrichKpiRow(d, staffMap);
      return d;
    });
  }

  saveKpi(
    projectId: number,
    payload: Record<string, unknown>,
    kpiId?: number,
    ts?: string,
  ): Record<string, unknown> {
    if (!this.tableExists('crm_re_project_kpis')) throw new Error('Bảng KPI chưa sẵn sàng.');
    const tsVal = ts ?? catalogTs();
    let cat = String(payload.category ?? 'sales');
    if (!(KPI_CATEGORIES as readonly string[]).includes(cat)) cat = 'sales';
    const nameRaw = String(payload.metric_name ?? '').trim();
    if (!nameRaw) throw new Error('Thiếu tên chỉ tiêu KPI.');
    const { staffId: ownerStaffId, ownerName } = this.resolveOwnerStaff(payload);
    let tr = String(payload.track_status ?? 'active');
    if (!(KPI_TRACK_STATUSES as readonly string[]).includes(tr)) tr = 'active';
    const unitInput = String(payload.unit ?? '').slice(0, 40);
    const { metricId, metricCode, name, unit } = this.resolveCrmMetric(payload, nameRaw, unitInput);
    const values = [
      cat,
      name.slice(0, 200),
      Number(payload.target_value ?? 0),
      Number(payload.actual_value ?? 0),
      unit.slice(0, 40),
      String(payload.period_month ?? '').slice(0, 7),
      Number(payload.weight_pct ?? 0),
      ownerStaffId,
      ownerName,
      tr,
      metricCode,
      metricId,
      String(payload.notes ?? '').slice(0, 2000),
      tsVal,
    ];

    let rid: number;
    if (kpiId) {
      this.database
        .prepare(
          `UPDATE crm_re_project_kpis SET
             category=?, metric_name=?, target_value=?, actual_value=?, unit=?,
             period_month=?, weight_pct=?, owner_staff_id=?, owner_name=?, track_status=?,
             metric_code=?, metric_id=?, notes=?, updated_at=?
           WHERE id=? AND project_id=?`,
        )
        .run(...values, kpiId, projectId);
      rid = kpiId;
    } else {
      const result = this.database
        .prepare(
          `INSERT INTO crm_re_project_kpis (
             project_id, category, metric_name, target_value, actual_value, unit,
             period_month, weight_pct, owner_staff_id, owner_name, track_status,
             metric_code, metric_id, notes, created_at, updated_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        )
        .run(projectId, ...values.slice(0, -1), tsVal, values[values.length - 1]);
      rid = Number(result.lastInsertRowid);
    }
    if (ownerStaffId && (metricId || metricCode)) {
      this.syncKpiToStaffModule(rid, projectId, tsVal);
    }
    const enriched = this.listKpis(projectId);
    const found = enriched.find((d) => Number(d.id) === rid);
    if (found) return found;
    const row = this.database.prepare('SELECT * FROM crm_re_project_kpis WHERE id = ?').get(rid) as
      | Record<string, unknown>
      | undefined;
    if (!row) throw new Error('Không lưu được KPI.');
    const d = { ...row } as Record<string, unknown>;
    this.enrichKpiRow(d, this.staffLookup(new Set([Number(d.owner_staff_id ?? 0)])));
    return d;
  }

  deleteKpi(projectId: number, kpiId: number): void {
    if (!this.tableExists('crm_re_project_kpis')) return;
    this.database
      .prepare('DELETE FROM crm_re_project_kpis WHERE id = ? AND project_id = ?')
      .run(kpiId, projectId);
  }

  listCrmKpiMetrics(reOnly = false): Array<Record<string, unknown>> {
    if (!this.tableExists('crm_kpi_metrics')) return [];
    try {
      const sql = reOnly
        ? `SELECT * FROM crm_kpi_metrics WHERE active = 1 AND code LIKE 'RE_%'
           ORDER BY sort_order ASC, name COLLATE NOCASE ASC`
        : `SELECT * FROM crm_kpi_metrics WHERE active = 1
           ORDER BY sort_order ASC, name COLLATE NOCASE ASC`;
      return this.database.prepare(sql).all() as Array<Record<string, unknown>>;
    } catch {
      return [];
    }
  }

  syncProjectKpisToStaff(projectId: number, ts?: string): Record<string, unknown> {
    if (!this.tableExists('crm_re_project_kpis')) return { synced: 0, skipped: 0, total: 0 };
    const rows = this.database
      .prepare('SELECT id FROM crm_re_project_kpis WHERE project_id = ? ORDER BY id')
      .all(projectId) as Array<{ id: number }>;
    let synced = 0;
    let skipped = 0;
    for (const r of rows) {
      if (this.syncKpiToStaffModule(Number(r.id), projectId, ts)) synced += 1;
      else skipped += 1;
    }
    return { synced, skipped, total: rows.length };
  }

  pullProjectKpisFromStaff(projectId: number, ts?: string): Record<string, unknown> {
    if (!this.tableExists('crm_re_project_kpis')) return { updated: 0, total_linked: 0 };
    const tsVal = ts ?? catalogTs();
    const rows = this.database
      .prepare('SELECT * FROM crm_re_project_kpis WHERE project_id = ? AND staff_kpi_id IS NOT NULL')
      .all(projectId) as Array<Record<string, unknown>>;
    let updated = 0;
    for (const r of rows) {
      try {
        const sk = this.database
          .prepare('SELECT actual_value, status FROM crm_staff_kpi WHERE id = ?')
          .get(Number(r.staff_kpi_id)) as { actual_value: number | null; status: string } | undefined;
        if (!sk) continue;
        const track = mapStaffToReTrackStatus(String(sk.status ?? 'draft'));
        this.database
          .prepare(
            `UPDATE crm_re_project_kpis
             SET actual_value = ?, track_status = ?, updated_at = ?
             WHERE id = ? AND project_id = ?`,
          )
          .run(Number(sk.actual_value ?? 0), track, tsVal, Number(r.id), projectId);
        updated += 1;
      } catch {
        /* skip row */
      }
    }
    return { updated, total_linked: rows.length };
  }

  private countProjectLeadsNewActual(projectId: number, periodMonth: string): number {
    if (!this.tableExists('crm_leads')) return 0;
    const pm = String(periodMonth || '').trim().slice(0, 7) || currentPeriodMonth();
    const excluded = [...RE_LEADS_NEW_EXCLUDED_STATUSES];
    const placeholders = excluded.map(() => '?').join(',');
    try {
      const row = this.database
        .prepare(
          `SELECT COUNT(*) AS c FROM crm_leads
           WHERE re_project_id = ?
             AND COALESCE(is_duplicate, 0) = 0
             AND status NOT IN (${placeholders})
             AND (
               substr(COALESCE(created_at, ''), 1, 7) = ?
               OR strftime('%Y-%m', created_at) = ?
             )`,
        )
        .get(projectId, ...excluded, pm, pm) as { c: number } | undefined;
      return Number(row?.c ?? 0);
    } catch {
      return 0;
    }
  }

  refreshProjectReLeadsNewKpi(
    projectId: number,
    options: { periodMonth?: string; ts?: string; syncStaff?: boolean } = {},
  ): Record<string, unknown> {
    this.validateProjectExists(projectId);
    const tsVal = options.ts ?? catalogTs();
    const pm = String(options.periodMonth ?? '').trim().slice(0, 7) || currentPeriodMonth();
    const actual = this.countProjectLeadsNewActual(projectId, pm);
    const existing = this.database
      .prepare(
        `SELECT id FROM crm_re_project_kpis
         WHERE project_id = ? AND metric_code = ? AND period_month = ?
         ORDER BY id DESC LIMIT 1`,
      )
      .get(projectId, RE_LEADS_NEW_METRIC_CODE, pm) as { id: number } | undefined;

    let kpiId: number | null = existing ? Number(existing.id) : null;
    if (kpiId) {
      this.database
        .prepare('UPDATE crm_re_project_kpis SET actual_value = ?, updated_at = ? WHERE id = ?')
        .run(actual, tsVal, kpiId);
    } else {
      const tmpl = KPI_METRIC_TEMPLATES.find((t) => t.crm_code === RE_LEADS_NEW_METRIC_CODE);
      if (tmpl) {
        const result = this.database
          .prepare(
            `INSERT INTO crm_re_project_kpis (
               project_id, category, metric_name, target_value, actual_value, unit,
               period_month, weight_pct, owner_name, track_status, metric_code,
               notes, created_at, updated_at
             ) VALUES (?, ?, ?, 0, ?, ?, ?, ?, '', 'active', ?, '', ?, ?)`,
          )
          .run(
            projectId,
            tmpl.category,
            tmpl.metric_name,
            actual,
            tmpl.unit,
            pm,
            tmpl.weight_pct,
            RE_LEADS_NEW_METRIC_CODE,
            tsVal,
            tsVal,
          );
        kpiId = Number(result.lastInsertRowid);
      }
    }
    if (options.syncStaff !== false && kpiId) {
      this.syncKpiToStaffModule(kpiId, projectId, tsVal);
    }
    return {
      updated: kpiId != null,
      kpi_id: kpiId,
      actual,
      period_month: pm,
      project_id: projectId,
    };
  }

  listRisks(projectId: number): Array<Record<string, unknown>> {
    if (!this.tableExists('crm_re_project_risks')) return [];
    const rows = this.database
      .prepare('SELECT * FROM crm_re_project_risks WHERE project_id = ? ORDER BY risk_level DESC, id')
      .all(projectId) as Array<Record<string, unknown>>;
    return rows.map((r) => {
      const d = { ...r } as Record<string, unknown>;
      const cat = String(d.category ?? '');
      const lv = String(d.risk_level ?? '');
      d.category_label = RISK_CATEGORY_LABELS[cat] ?? cat;
      d.risk_level_label = RISK_LEVEL_LABELS[lv] ?? lv;
      d.score =
        Math.round((Number(d.probability_pct ?? 0) * Number(d.impact_pct ?? 0)) / 100 * 10) / 10;
      return d;
    });
  }

  saveRisk(
    projectId: number,
    payload: Record<string, unknown>,
    riskId?: number,
    ts?: string,
  ): Record<string, unknown> {
    if (!this.tableExists('crm_re_project_risks')) throw new Error('Bảng rủi ro chưa sẵn sàng.');
    const tsVal = ts ?? catalogTs();
    const title = String(payload.title ?? '').trim();
    if (!title) throw new Error('Thiếu tiêu đề rủi ro.');
    let cat = String(payload.category ?? 'market');
    if (!(RISK_CATEGORIES as readonly string[]).includes(cat)) cat = 'market';
    let lv = String(payload.risk_level ?? 'medium');
    if (!(RISK_LEVELS as readonly string[]).includes(lv)) lv = 'medium';

    let rid: number;
    if (riskId) {
      this.database
        .prepare(
          `UPDATE crm_re_project_risks SET
             category=?, title=?, description=?, probability_pct=?, impact_pct=?,
             risk_level=?, mitigation=?, owner_name=?, status=?, due_date=?, updated_at=?
           WHERE id=? AND project_id=?`,
        )
        .run(
          cat,
          title.slice(0, 200),
          String(payload.description ?? '').slice(0, 4000),
          Number(payload.probability_pct ?? 0),
          Number(payload.impact_pct ?? 0),
          lv,
          String(payload.mitigation ?? '').slice(0, 4000),
          String(payload.owner_name ?? '').slice(0, 120),
          String(payload.status ?? 'open').slice(0, 40),
          String(payload.due_date ?? '').slice(0, 10),
          tsVal,
          riskId,
          projectId,
        );
      rid = riskId;
    } else {
      const result = this.database
        .prepare(
          `INSERT INTO crm_re_project_risks (
             project_id, category, title, description, probability_pct, impact_pct,
             risk_level, mitigation, owner_name, status, due_date, created_at, updated_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        )
        .run(
          projectId,
          cat,
          title.slice(0, 200),
          String(payload.description ?? '').slice(0, 4000),
          Number(payload.probability_pct ?? 0),
          Number(payload.impact_pct ?? 0),
          lv,
          String(payload.mitigation ?? '').slice(0, 4000),
          String(payload.owner_name ?? '').slice(0, 120),
          String(payload.status ?? 'open').slice(0, 40),
          String(payload.due_date ?? '').slice(0, 10),
          tsVal,
          tsVal,
        );
      rid = Number(result.lastInsertRowid);
    }
    const row = this.database.prepare('SELECT * FROM crm_re_project_risks WHERE id = ?').get(rid) as
      | Record<string, unknown>
      | undefined;
    if (!row) throw new Error('Không lưu được rủi ro.');
    const d = { ...row } as Record<string, unknown>;
    const catOut = String(d.category ?? '');
    const lvOut = String(d.risk_level ?? '');
    d.category_label = RISK_CATEGORY_LABELS[catOut] ?? catOut;
    d.risk_level_label = RISK_LEVEL_LABELS[lvOut] ?? lvOut;
    d.score =
      Math.round((Number(d.probability_pct ?? 0) * Number(d.impact_pct ?? 0)) / 100 * 10) / 10;
    return d;
  }

  deleteRisk(projectId: number, riskId: number): void {
    if (!this.tableExists('crm_re_project_risks')) return;
    this.database
      .prepare('DELETE FROM crm_re_project_risks WHERE id = ? AND project_id = ?')
      .run(riskId, projectId);
  }

  listBudgetLines(projectId: number): Array<Record<string, unknown>> {
    if (!this.tableExists('crm_re_project_budget_lines')) return [];
    const rows = this.database
      .prepare(
        'SELECT * FROM crm_re_project_budget_lines WHERE project_id = ? ORDER BY period_month, category, id',
      )
      .all(projectId) as Array<Record<string, unknown>>;
    return rows.map((r) => {
      const d = { ...r } as Record<string, unknown>;
      const cat = String(d.category ?? '');
      d.category_label = BUDGET_CATEGORY_LABELS[cat] ?? cat;
      const pl = Number(d.planned_vnd ?? 0);
      const ac = Number(d.actual_vnd ?? 0);
      d.variance_vnd = ac - pl;
      d.variance_pct = pl ? Math.round(((ac - pl) / pl) * 1000) / 10 : 0;
      return d;
    });
  }

  saveBudgetLine(
    projectId: number,
    payload: Record<string, unknown>,
    lineId?: number,
    ts?: string,
  ): Record<string, unknown> {
    if (!this.tableExists('crm_re_project_budget_lines')) {
      throw new Error('Bảng ngân sách chưa sẵn sàng.');
    }
    const tsVal = ts ?? catalogTs();
    const item = String(payload.line_item ?? '').trim();
    if (!item) throw new Error('Thiếu hạng mục ngân sách.');
    let cat = String(payload.category ?? 'revenue');
    if (!(BUDGET_CATEGORIES as readonly string[]).includes(cat)) cat = 'revenue';

    let rid: number;
    if (lineId) {
      this.database
        .prepare(
          `UPDATE crm_re_project_budget_lines SET
             category=?, line_item=?, period_month=?, planned_vnd=?, actual_vnd=?, notes=?, updated_at=?
           WHERE id=? AND project_id=?`,
        )
        .run(
          cat,
          item.slice(0, 200),
          String(payload.period_month ?? '').slice(0, 7),
          Number(payload.planned_vnd ?? 0),
          Number(payload.actual_vnd ?? 0),
          String(payload.notes ?? '').slice(0, 2000),
          tsVal,
          lineId,
          projectId,
        );
      rid = lineId;
    } else {
      const result = this.database
        .prepare(
          `INSERT INTO crm_re_project_budget_lines (
             project_id, category, line_item, period_month, planned_vnd, actual_vnd, notes, created_at, updated_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        )
        .run(
          projectId,
          cat,
          item.slice(0, 200),
          String(payload.period_month ?? '').slice(0, 7),
          Number(payload.planned_vnd ?? 0),
          Number(payload.actual_vnd ?? 0),
          String(payload.notes ?? '').slice(0, 2000),
          tsVal,
          tsVal,
        );
      rid = Number(result.lastInsertRowid);
    }
    const row = this.database.prepare('SELECT * FROM crm_re_project_budget_lines WHERE id = ?').get(rid) as
      | Record<string, unknown>
      | undefined;
    if (!row) throw new Error('Không lưu được dòng ngân sách.');
    const d = { ...row } as Record<string, unknown>;
    const catOut = String(d.category ?? '');
    d.category_label = BUDGET_CATEGORY_LABELS[catOut] ?? catOut;
    const pl = Number(d.planned_vnd ?? 0);
    const ac = Number(d.actual_vnd ?? 0);
    d.variance_vnd = ac - pl;
    d.variance_pct = pl ? Math.round(((ac - pl) / pl) * 1000) / 10 : 0;
    return d;
  }

  deleteBudgetLine(projectId: number, lineId: number): void {
    if (!this.tableExists('crm_re_project_budget_lines')) return;
    this.database
      .prepare('DELETE FROM crm_re_project_budget_lines WHERE id = ? AND project_id = ?')
      .run(lineId, projectId);
  }

  fetchProjectSummary(projectId: number): Record<string, unknown> {
    const proj = this.fetchProject(projectId);
    if (!proj) throw new Error('Không tìm thấy dự án.');
    const products = this.listProducts(projectId);
    const kpis = this.listKpis(projectId);
    const risks = this.listRisks(projectId);
    const budget = this.listBudgetLines(projectId);
    const revPlanned = budget
      .filter((b) => b.category === 'revenue')
      .reduce((s, b) => s + Number(b.planned_vnd ?? 0), 0);
    const revActual = budget
      .filter((b) => b.category === 'revenue')
      .reduce((s, b) => s + Number(b.actual_vnd ?? 0), 0);
    const costPlanned = budget
      .filter((b) => b.category !== 'revenue')
      .reduce((s, b) => s + Number(b.planned_vnd ?? 0), 0);
    const costActual = budget
      .filter((b) => b.category !== 'revenue')
      .reduce((s, b) => s + Number(b.actual_vnd ?? 0), 0);
    const highRisks = risks.filter((r) => r.risk_level === 'high' || r.risk_level === 'critical').length;
    let kpiAvg = 0;
    let kpiWithOwner = 0;
    if (kpis.length) {
      kpiAvg =
        Math.round(
          (kpis.reduce((s, k) => s + Number(k.achievement_pct ?? 0), 0) / kpis.length) * 10,
        ) / 10;
      kpiWithOwner = kpis.filter(
        (k) => Number(k.owner_staff_id ?? 0) > 0 || String(k.owner_name ?? '').trim(),
      ).length;
    }
    const inv = computeProductInventoryStats(products);
    const kpiBoard = computeKpiBoardStats(kpis);
    return {
      project: proj,
      product_count: products.length,
      products_available: products.filter((p) => p.status === 'available').length,
      products_sold: products.filter((p) => p.status === 'sold').length,
      product_lines_count: (inv.by_product_line as unknown[])?.length ?? 0,
      product_zones_count: (inv.by_zone as unknown[])?.length ?? 0,
      kpi_count: kpis.length,
      kpi_with_owner_count: kpiWithOwner,
      kpi_avg_achievement_pct: kpiAvg,
      kpi_weight_total_pct: kpiBoard.weight_total_pct ?? 0,
      inventory: inv,
      kpi_board: kpiBoard,
      risk_count: risks.length,
      high_risk_count: highRisks,
      budget_revenue_planned_vnd: revPlanned,
      budget_revenue_actual_vnd: revActual,
      budget_cost_planned_vnd: costPlanned,
      budget_cost_actual_vnd: costActual,
      profit_planned_vnd: revPlanned - costPlanned,
      profit_actual_vnd: revActual - costActual,
    };
  }

  listProjectZones(projectId: number): string[] {
    if (!this.tableExists('crm_re_project_products')) return [];
    const rows = this.database
      .prepare(
        `SELECT DISTINCT trim(zone) AS z FROM crm_re_project_products
         WHERE project_id = ? AND trim(COALESCE(zone, '')) != ''
         ORDER BY z COLLATE NOCASE`,
      )
      .all(projectId) as Array<{ z: string }>;
    return rows.map((r) => String(r.z)).filter(Boolean);
  }

  inventoryByZoneSummary(projectId: number): Array<Record<string, unknown>> {
    const products = this.listProducts(projectId);
    const inv = computeProductInventoryStats(products);
    const byZone = (inv.by_zone as Array<Record<string, unknown>>) ?? [];
    const byLine: Record<string, Record<string, unknown>> = {};
    for (const r of (inv.by_product_line as Array<Record<string, unknown>>) ?? []) {
      byLine[String(r.key)] = r;
    }
    return byZone.map((z) => {
      const zoneKey = String(z.key ?? '');
      const zoneProducts = products.filter(
        (p) => (String(p.zone ?? '').trim() || 'Chưa phân khu') === zoneKey,
      );
      const lineCounts: Record<string, number> = {};
      for (const p of zoneProducts) {
        const lk = String(p.product_line ?? 'other');
        lineCounts[lk] = (lineCounts[lk] ?? 0) + 1;
      }
      const linesDetail = Object.entries(lineCounts)
        .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
        .map(([lk, cnt]) => ({
          product_line: lk,
          label: PRODUCT_LINE_LABELS[lk] ?? lk,
          count: cnt,
          stats: byLine[lk],
        }));
      return { ...z, product_lines: linesDetail };
    });
  }

  listPriceBatches(projectId: number): string[] {
    if (!this.tableExists('crm_re_project_products')) return [];
    const rows = this.database
      .prepare(
        `SELECT DISTINCT trim(price_batch) AS b FROM crm_re_project_products
         WHERE project_id = ? AND trim(COALESCE(price_batch, '')) != ''
         ORDER BY b COLLATE NOCASE DESC`,
      )
      .all(projectId) as Array<{ b: string }>;
    return rows.map((r) => String(r.b)).filter(Boolean);
  }

  inventoryByPriceBatchSummary(projectId: number): Array<Record<string, unknown>> {
    const products = this.listProducts(projectId);
    const batches: Record<string, Record<string, unknown>> = {};
    for (const p of products) {
      const key = String(p.price_batch ?? '').trim() || 'Chưa gán đợt';
      if (!batches[key]) {
        batches[key] = {
          key,
          label: key,
          total: 0,
          available: 0,
          sold: 0,
          hold: 0,
          booked: 0,
        };
      }
      const bucket = batches[key];
      bucket.total = Number(bucket.total) + 1;
      const st = String(p.status ?? 'available');
      if (st === 'available') bucket.available = Number(bucket.available) + 1;
      else if (st === 'sold') bucket.sold = Number(bucket.sold) + 1;
      else if (st === 'hold') bucket.hold = Number(bucket.hold) + 1;
      else if (st === 'booked') bucket.booked = Number(bucket.booked) + 1;
    }
    return Object.values(batches);
  }

  private mapPriceListRow(row: Record<string, unknown>): RePriceListRow {
    let st = String(row.status ?? 'draft');
    if (!(PRICE_LIST_STATUSES as readonly string[]).includes(st)) st = 'draft';
    return {
      id: Number(row.id),
      project_id: Number(row.project_id),
      version_code: String(row.version_code ?? ''),
      name: String(row.name ?? ''),
      effective_date: String(row.effective_date ?? ''),
      status: st,
      status_label: PRICE_LIST_STATUS_LABELS[st] ?? st,
      notes: String(row.notes ?? ''),
      applied_at: String(row.applied_at ?? ''),
      applied_by: String(row.applied_by ?? ''),
      created_by: String(row.created_by ?? ''),
      created_at: String(row.created_at ?? ''),
      updated_at: String(row.updated_at ?? ''),
      item_count: Number(row.item_count ?? 0),
    };
  }

  private validateProjectExists(projectId: number): void {
    const row = this.fetchProject(projectId);
    if (!row) throw new Error('Không tìm thấy dự án.');
  }

  listPriceLists(projectId: number): RePriceListRow[] {
    if (!this.tableExists('crm_re_price_lists')) return [];
    const rows = this.database
      .prepare(
        `SELECT pl.*,
                (SELECT COUNT(*) FROM crm_re_price_list_items i WHERE i.price_list_id = pl.id) AS item_count
         FROM crm_re_price_lists pl
         WHERE pl.project_id = ?
         ORDER BY pl.effective_date DESC, pl.updated_at DESC, pl.id DESC`,
      )
      .all(projectId) as Array<Record<string, unknown>>;
    return rows.map((r) => this.mapPriceListRow(r));
  }

  fetchPriceList(projectId: number, listId: number): RePriceListRow | null {
    if (!this.tableExists('crm_re_price_lists')) return null;
    const row = this.database
      .prepare(
        `SELECT pl.*,
                (SELECT COUNT(*) FROM crm_re_price_list_items i WHERE i.price_list_id = pl.id) AS item_count
         FROM crm_re_price_lists pl
         WHERE pl.id = ? AND pl.project_id = ?`,
      )
      .get(listId, projectId) as Record<string, unknown> | undefined;
    return row ? this.mapPriceListRow(row) : null;
  }

  listPriceListItems(priceListId: number, limit = 500, offset = 0): {
    items: Array<Record<string, unknown>>;
    total: number;
  } {
    if (!this.tableExists('crm_re_price_list_items')) return { items: [], total: 0 };
    const lim = Math.max(1, Math.min(limit, 2000));
    const off = Math.max(0, offset);
    const totalRow = this.database
      .prepare('SELECT COUNT(*) AS c FROM crm_re_price_list_items WHERE price_list_id = ?')
      .get(priceListId) as { c: number } | undefined;
    const total = Number(totalRow?.c ?? 0);
    const rows = this.database
      .prepare(
        `SELECT * FROM crm_re_price_list_items
         WHERE price_list_id = ?
         ORDER BY unit_code COLLATE NOCASE
         LIMIT ? OFFSET ?`,
      )
      .all(priceListId, lim, off) as Array<Record<string, unknown>>;
    const items = rows.map((d) => ({
      id: Number(d.id),
      price_list_id: Number(d.price_list_id),
      unit_code: String(d.unit_code ?? ''),
      zone: String(d.zone ?? ''),
      list_price_vnd: Number(d.list_price_vnd ?? 0),
      net_price_vnd: Number(d.net_price_vnd ?? 0),
      notes: String(d.notes ?? ''),
      created_at: String(d.created_at ?? ''),
      updated_at: String(d.updated_at ?? ''),
    }));
    return { items, total };
  }

  savePriceList(
    projectId: number,
    payload: SavePriceListBody,
    listId?: number,
    createdBy = '',
  ): RePriceListRow {
    if (!this.tableExists('crm_re_price_lists')) throw new Error('Bảng giá chưa sẵn sàng.');
    this.validateProjectExists(projectId);
    const ts = catalogTs();
    const versionCode = String(payload.version_code ?? payload.code ?? '').trim().slice(0, 80);
    if (!versionCode) throw new Error('Thiếu mã version (version_code).');
    const name = String(payload.name ?? versionCode).trim().slice(0, 200);
    const effectiveDate = String(payload.effective_date ?? '').trim().slice(0, 10);
    const notes = String(payload.notes ?? '').slice(0, 2000);

    let rid: number;
    if (listId) {
      const existing = this.fetchPriceList(projectId, listId);
      if (!existing) throw new Error('Không tìm thấy bảng giá.');
      if (existing.status === 'active' && payload.version_code) {
        const dup = this.database
          .prepare(
            `SELECT id FROM crm_re_price_lists
             WHERE project_id = ? AND lower(trim(version_code)) = lower(?) AND id != ?`,
          )
          .get(projectId, versionCode, listId);
        if (dup) throw new Error(`Mã version «${versionCode}» đã tồn tại.`);
      }
      let status = existing.status;
      if (payload.status != null) {
        const newSt = String(payload.status).trim().toLowerCase();
        if (!(PRICE_LIST_STATUSES as readonly string[]).includes(newSt)) {
          throw new Error(`Trạng thái không hợp lệ: ${payload.status}`);
        }
        if (newSt === 'active' && existing.status !== 'active') {
          throw new Error('Dùng «Áp dụng bảng giá» để kích hoạt — không đổi status trực tiếp.');
        }
        if (existing.status !== 'active') status = newSt;
      }
      this.database
        .prepare(
          `UPDATE crm_re_price_lists SET
             version_code = ?, name = ?, effective_date = ?, status = ?, notes = ?, updated_at = ?
           WHERE id = ? AND project_id = ?`,
        )
        .run(versionCode, name, effectiveDate, status, notes, ts, listId, projectId);
      rid = listId;
    } else {
      const dup = this.database
        .prepare(
          `SELECT id FROM crm_re_price_lists
           WHERE project_id = ? AND lower(trim(version_code)) = lower(?)`,
        )
        .get(projectId, versionCode);
      if (dup) throw new Error(`Mã version «${versionCode}» đã tồn tại.`);
      const result = this.database
        .prepare(
          `INSERT INTO crm_re_price_lists (
             project_id, version_code, name, effective_date, status, notes,
             applied_at, applied_by, created_by, created_at, updated_at
           ) VALUES (?, ?, ?, ?, 'draft', ?, '', '', ?, ?, ?)`,
        )
        .run(projectId, versionCode, name, effectiveDate, notes, String(createdBy).slice(0, 120), ts, ts);
      rid = Number(result.lastInsertRowid);
    }
    const out = this.fetchPriceList(projectId, rid);
    if (!out) throw new Error('Không tìm thấy bảng giá sau khi lưu.');
    return out;
  }

  deletePriceList(projectId: number, listId: number): void {
    const row = this.fetchPriceList(projectId, listId);
    if (!row) throw new Error('Không tìm thấy bảng giá.');
    if (row.status === 'active') {
      throw new Error('Không xóa bảng giá đang áp dụng — lưu trữ hoặc áp bảng khác trước.');
    }
    this.database
      .prepare('DELETE FROM crm_re_price_lists WHERE id = ? AND project_id = ?')
      .run(listId, projectId);
  }

  listAllVersionCodes(projectId: number): string[] {
    const codes = new Set<string>();
    for (const pl of this.listPriceLists(projectId)) {
      const c = String(pl.version_code ?? '').trim();
      if (c) codes.add(c);
    }
    for (const b of this.listPriceBatches(projectId)) {
      if (b) codes.add(b);
    }
    return [...codes].sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
  }

  private normalizeStaffRole(role: string): string {
    const r = String(role || 'sales').trim().toLowerCase();
    return (PROJECT_STAFF_ROLES as readonly string[]).includes(r) ? r : 'sales';
  }

  private scopeListToJson(items: string[] | undefined): string {
    const out = (items ?? []).map((x) => String(x).trim()).filter(Boolean);
    return JSON.stringify(out);
  }

  private parseScopeList(raw: unknown): string[] {
    if (Array.isArray(raw)) return raw.map((x) => String(x).trim()).filter(Boolean);
    if (typeof raw === 'string' && raw.trim()) {
      try {
        const parsed = JSON.parse(raw) as unknown;
        if (Array.isArray(parsed)) return parsed.map((x) => String(x).trim()).filter(Boolean);
      } catch {
        /* ignore */
      }
    }
    return [];
  }

  private enrichStaffScopeFields(d: Record<string, unknown>): ReProjectStaffRow {
    const scopeLines = this.parseScopeList(d.scope_product_lines);
    const scopeZones = this.parseScopeList(d.scope_zones);
    const role = this.normalizeStaffRole(String(d.role ?? 'sales'));
    return {
      id: Number(d.id),
      project_id: Number(d.project_id),
      staff_id: Number(d.staff_id),
      staff_name: String(d.staff_name ?? ''),
      staff_code: String(d.staff_code ?? ''),
      role,
      role_label: PROJECT_STAFF_ROLE_LABELS[role] ?? role,
      assign_enabled: Boolean(Number(d.assign_enabled ?? 0)),
      sort_order: Number(d.sort_order ?? 0),
      joined_at: String(d.joined_at ?? ''),
      left_at: d.left_at ? String(d.left_at) : null,
      active: !d.left_at,
      scope_product_lines: scopeLines,
      scope_zones: scopeZones,
      scope_product_lines_label: scopeLines.length
        ? scopeLines.map((x) => PRODUCT_LINE_LABELS[x] ?? x).join(', ')
        : 'Tất cả dòng SP',
      scope_zones_label: scopeZones.length ? scopeZones.join(', ') : 'Tất cả phân khu',
    };
  }

  private ensureProjectStaffSchema(): void {
    if (!this.tableExists('crm_re_project_staff')) {
      this.database.exec(`
        CREATE TABLE IF NOT EXISTS crm_re_project_staff (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          project_id INTEGER NOT NULL,
          staff_id INTEGER NOT NULL,
          role TEXT NOT NULL DEFAULT 'sales',
          assign_enabled INTEGER NOT NULL DEFAULT 1,
          sort_order INTEGER NOT NULL DEFAULT 0,
          scope_product_lines TEXT NOT NULL DEFAULT '[]',
          scope_zones TEXT NOT NULL DEFAULT '[]',
          joined_at TEXT NOT NULL DEFAULT '',
          left_at TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(project_id, staff_id)
        )
      `);
    }
  }

  private ensureProjectLeadConfigSchema(): void {
    if (!this.tableExists('crm_re_project_lead_config')) {
      this.database.exec(`
        CREATE TABLE IF NOT EXISTS crm_re_project_lead_config (
          project_id INTEGER PRIMARY KEY,
          enabled INTEGER NOT NULL DEFAULT 1,
          webhook_slug TEXT NOT NULL DEFAULT '',
          webhook_verify_token TEXT NOT NULL DEFAULT '',
          facebook_page_id TEXT NOT NULL DEFAULT '',
          zalo_oa_id TEXT NOT NULL DEFAULT '',
          auto_assign INTEGER NOT NULL DEFAULT 1,
          webhook_enabled INTEGER NOT NULL DEFAULT 1,
          updated_at TEXT NOT NULL DEFAULT '',
          updated_by TEXT NOT NULL DEFAULT ''
        )
      `);
    }
    if (!this.tableExists('crm_re_project_facebook_forms')) {
      this.database.exec(`
        CREATE TABLE IF NOT EXISTS crm_re_project_facebook_forms (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          project_id INTEGER NOT NULL,
          page_id TEXT NOT NULL DEFAULT '',
          form_id TEXT NOT NULL UNIQUE,
          form_name TEXT NOT NULL DEFAULT '',
          active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL DEFAULT '',
          updated_at TEXT NOT NULL DEFAULT ''
        )
      `);
    }
    if (!this.tableExists('crm_re_project_zalo_campaigns')) {
      this.database.exec(`
        CREATE TABLE IF NOT EXISTS crm_re_project_zalo_campaigns (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          project_id INTEGER NOT NULL,
          oa_id TEXT NOT NULL DEFAULT '',
          campaign_id TEXT NOT NULL UNIQUE,
          campaign_name TEXT NOT NULL DEFAULT '',
          active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL DEFAULT '',
          updated_at TEXT NOT NULL DEFAULT ''
        )
      `);
    }
    if (!this.tableExists('crm_re_project_website_routes')) {
      this.database.exec(`
        CREATE TABLE IF NOT EXISTS crm_re_project_website_routes (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          project_id INTEGER NOT NULL,
          route_key TEXT NOT NULL UNIQUE,
          route_name TEXT NOT NULL DEFAULT '',
          route_type TEXT NOT NULL DEFAULT 'utm',
          active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL DEFAULT '',
          updated_at TEXT NOT NULL DEFAULT ''
        )
      `);
    }
  }

  private facebookWebhookCallbackUrl(): string {
    return (
      process.env.CRM_FACEBOOK_WEBHOOK_URL ??
      process.env.FACEBOOK_WEBHOOK_URL ??
      'https://pttads.vn/api/crm/integration/webhooks/facebook'
    )
      .trim()
      .replace(/\/+$/, '');
  }

  private zaloWebhookCallbackUrl(): string {
    return (
      process.env.CRM_ZALO_WEBHOOK_URL ??
      process.env.ZALO_WEBHOOK_URL ??
      'https://pttads.vn/api/crm/integration/webhooks/zalo'
    )
      .trim()
      .replace(/\/+$/, '');
  }

  private defaultWebhookSlug(projectId: number): string {
    const suffix = randomBytes(4).toString('hex').slice(0, 8);
    return `p${projectId}-${suffix}`;
  }

  private projectWebhookUrl(slug: string): string {
    const base = this.facebookWebhookCallbackUrl();
    const s = String(slug ?? '').trim().replace(/^\/+|\/+$/g, '');
    return s ? `${base}/${s}` : base;
  }

  private projectZaloWebhookUrl(slug: string): string {
    const base = this.zaloWebhookCallbackUrl();
    const s = String(slug ?? '').trim().replace(/^\/+|\/+$/g, '');
    return s ? `${base}/${s}` : base;
  }

  private listProjectFacebookForms(projectId: number): Array<Record<string, unknown>> {
    if (!this.tableExists('crm_re_project_facebook_forms')) return [];
    const rows = this.database
      .prepare(
        `SELECT id, project_id, page_id, form_id, form_name, active, created_at, updated_at
         FROM crm_re_project_facebook_forms WHERE project_id = ? ORDER BY form_name, form_id`,
      )
      .all(projectId) as Array<Record<string, unknown>>;
    return rows.map((r) => ({
      id: Number(r.id),
      project_id: Number(r.project_id),
      page_id: String(r.page_id ?? ''),
      form_id: String(r.form_id ?? ''),
      form_name: String(r.form_name ?? ''),
      active: Boolean(Number(r.active ?? 0)),
      created_at: String(r.created_at ?? ''),
      updated_at: String(r.updated_at ?? ''),
    }));
  }

  private listProjectZaloCampaigns(projectId: number): Array<Record<string, unknown>> {
    if (!this.tableExists('crm_re_project_zalo_campaigns')) return [];
    const rows = this.database
      .prepare(
        `SELECT id, project_id, oa_id, campaign_id, campaign_name, active, created_at, updated_at
         FROM crm_re_project_zalo_campaigns WHERE project_id = ? ORDER BY campaign_name, campaign_id`,
      )
      .all(projectId) as Array<Record<string, unknown>>;
    return rows.map((r) => ({
      id: Number(r.id),
      project_id: Number(r.project_id),
      oa_id: String(r.oa_id ?? ''),
      campaign_id: String(r.campaign_id ?? ''),
      campaign_name: String(r.campaign_name ?? ''),
      active: Boolean(Number(r.active ?? 0)),
      created_at: String(r.created_at ?? ''),
      updated_at: String(r.updated_at ?? ''),
    }));
  }

  private listProjectWebsiteRoutes(projectId: number): Array<Record<string, unknown>> {
    if (!this.tableExists('crm_re_project_website_routes')) return [];
    const rows = this.database
      .prepare(
        `SELECT id, project_id, route_key, route_name, route_type, active, created_at, updated_at
         FROM crm_re_project_website_routes WHERE project_id = ? ORDER BY route_name, route_key`,
      )
      .all(projectId) as Array<Record<string, unknown>>;
    return rows.map((r) => ({
      id: Number(r.id),
      project_id: Number(r.project_id),
      route_key: String(r.route_key ?? ''),
      route_name: String(r.route_name ?? ''),
      route_type: String(r.route_type ?? 'utm'),
      active: Boolean(Number(r.active ?? 0)),
      created_at: String(r.created_at ?? ''),
      updated_at: String(r.updated_at ?? ''),
    }));
  }

  private leadConfigRowToDict(
    row: Record<string, unknown> | undefined,
    projectId: number,
  ): ReProjectLeadConfigRow {
    if (!row) {
      const slug = this.defaultWebhookSlug(projectId);
      return {
        project_id: projectId,
        enabled: true,
        webhook_slug: slug,
        webhook_verify_token: '',
        webhook_url: this.projectWebhookUrl(slug),
        zalo_webhook_url: this.projectZaloWebhookUrl(slug),
        facebook_page_id: '',
        zalo_oa_id: '',
        auto_assign: true,
        webhook_enabled: true,
        forms: [],
        zalo_campaigns: [],
        website_routes: [],
        updated_at: '',
        updated_by: '',
      };
    }
    const slug = String(row.webhook_slug ?? '').trim() || this.defaultWebhookSlug(projectId);
    return {
      project_id: Number(row.project_id),
      enabled: Boolean(Number(row.enabled ?? 0)),
      webhook_slug: slug,
      webhook_verify_token: String(row.webhook_verify_token ?? ''),
      webhook_url: this.projectWebhookUrl(slug),
      zalo_webhook_url: this.projectZaloWebhookUrl(slug),
      facebook_page_id: String(row.facebook_page_id ?? ''),
      zalo_oa_id: String(row.zalo_oa_id ?? ''),
      auto_assign: Boolean(Number(row.auto_assign ?? 1)),
      webhook_enabled: Boolean(Number(row.webhook_enabled ?? 1)),
      forms: this.listProjectFacebookForms(projectId),
      zalo_campaigns: this.listProjectZaloCampaigns(projectId),
      website_routes: this.listProjectWebsiteRoutes(projectId),
      updated_at: String(row.updated_at ?? ''),
      updated_by: String(row.updated_by ?? ''),
    };
  }

  listProjectStaff(projectId: number, activeOnly = true): ReProjectStaffRow[] {
    this.validateProjectExists(projectId);
    this.ensureProjectStaffSchema();
    const clauses = ['ps.project_id = ?'];
    const params: Array<string | number> = [projectId];
    if (activeOnly) clauses.push('ps.left_at IS NULL');
    const rows = this.database
      .prepare(
        `SELECT ps.*, s.name AS staff_name, s.internal_code AS staff_code
         FROM crm_re_project_staff ps
         JOIN crm_staff s ON s.id = ps.staff_id
         WHERE ${clauses.join(' AND ')}
         ORDER BY ps.sort_order ASC, ps.id ASC`,
      )
      .all(...params) as Array<Record<string, unknown>>;
    return rows.map((r) => this.enrichStaffScopeFields(r));
  }

  addProjectStaff(
    projectId: number,
    payload: {
      staff_id: number;
      role?: string;
      assign_enabled?: boolean | number | string;
      sort_order?: number;
      scope_product_lines?: string[];
      scope_zones?: string[];
    },
  ): ReProjectStaffRow {
    this.validateProjectExists(projectId);
    this.ensureProjectStaffSchema();
    const sid = Number(payload.staff_id);
    const staff = this.database
      .prepare('SELECT id FROM crm_staff WHERE id = ? AND COALESCE(active, 1) = 1')
      .get(sid);
    if (!staff) throw new Error('Nhân viên không hợp lệ hoặc đã ngưng.');
    const ts = catalogTs();
    const roleNorm = this.normalizeStaffRole(String(payload.role ?? 'sales'));
    const assignEnabled = payload.assign_enabled === false || payload.assign_enabled === 0 ? 0 : 1;
    const sortOrder = Number(payload.sort_order ?? 0);
    const scopeLinesJson = this.scopeListToJson(payload.scope_product_lines);
    const scopeZonesJson = this.scopeListToJson(payload.scope_zones);
    const existing = this.database
      .prepare('SELECT id, left_at FROM crm_re_project_staff WHERE project_id = ? AND staff_id = ?')
      .get(projectId, sid) as { id: number; left_at: string | null } | undefined;
    let rowId: number;
    if (existing) {
      this.database
        .prepare(
          `UPDATE crm_re_project_staff SET
             role = ?, assign_enabled = ?, sort_order = ?,
             scope_product_lines = ?, scope_zones = ?,
             left_at = NULL, joined_at = ?, updated_at = ?
           WHERE id = ?`,
        )
        .run(roleNorm, assignEnabled, sortOrder, scopeLinesJson, scopeZonesJson, ts, ts, existing.id);
      rowId = existing.id;
    } else {
      const result = this.database
        .prepare(
          `INSERT INTO crm_re_project_staff (
             project_id, staff_id, role, assign_enabled, sort_order,
             scope_product_lines, scope_zones, joined_at, left_at, created_at, updated_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)`,
        )
        .run(projectId, sid, roleNorm, assignEnabled, sortOrder, scopeLinesJson, scopeZonesJson, ts, ts, ts);
      rowId = Number(result.lastInsertRowid);
    }
    const row = this.database
      .prepare(
        `SELECT ps.*, s.name AS staff_name, s.internal_code AS staff_code
         FROM crm_re_project_staff ps
         JOIN crm_staff s ON s.id = ps.staff_id
         WHERE ps.id = ?`,
      )
      .get(rowId) as Record<string, unknown>;
    return this.enrichStaffScopeFields(row);
  }

  updateProjectStaff(
    projectId: number,
    staffId: number,
    body: UpdateProjectStaffBody,
  ): ReProjectStaffRow {
    this.ensureProjectStaffSchema();
    const row = this.database
      .prepare(
        `SELECT id FROM crm_re_project_staff
         WHERE project_id = ? AND staff_id = ? AND left_at IS NULL`,
      )
      .get(projectId, staffId) as { id: number } | undefined;
    if (!row) throw new Error('Nhân viên không còn trong dự án.');
    const ts = catalogTs();
    const sets = ['updated_at = ?'];
    const params: Array<string | number | null> = [ts];
    if (body.role != null) {
      sets.push('role = ?');
      params.push(this.normalizeStaffRole(String(body.role)));
    }
    if (body.assign_enabled != null) {
      sets.push('assign_enabled = ?');
      params.push(body.assign_enabled === false || body.assign_enabled === 0 ? 0 : 1);
    }
    if (body.sort_order != null) {
      sets.push('sort_order = ?');
      params.push(Number(body.sort_order ?? 0));
    }
    if (body.scope_product_lines != null) {
      sets.push('scope_product_lines = ?');
      params.push(this.scopeListToJson(body.scope_product_lines));
    }
    if (body.scope_zones != null) {
      sets.push('scope_zones = ?');
      params.push(this.scopeListToJson(body.scope_zones));
    }
    params.push(row.id);
    this.database.prepare(`UPDATE crm_re_project_staff SET ${sets.join(', ')} WHERE id = ?`).run(...params);
    const out = this.database
      .prepare(
        `SELECT ps.*, s.name AS staff_name, s.internal_code AS staff_code
         FROM crm_re_project_staff ps
         JOIN crm_staff s ON s.id = ps.staff_id
         WHERE ps.id = ?`,
      )
      .get(row.id) as Record<string, unknown>;
    return this.enrichStaffScopeFields(out);
  }

  removeProjectStaff(projectId: number, staffId: number): void {
    this.ensureProjectStaffSchema();
    const ts = catalogTs();
    const result = this.database
      .prepare(
        `UPDATE crm_re_project_staff SET left_at = ?, updated_at = ?
         WHERE project_id = ? AND staff_id = ? AND left_at IS NULL`,
      )
      .run(ts, ts, projectId, staffId);
    if (!result.changes) throw new Error('Nhân viên không còn trong dự án.');
  }

  getProjectLeadConfig(projectId: number): ReProjectLeadConfigRow {
    this.validateProjectExists(projectId);
    this.ensureProjectLeadConfigSchema();
    const row = this.database
      .prepare('SELECT * FROM crm_re_project_lead_config WHERE project_id = ?')
      .get(projectId) as Record<string, unknown> | undefined;
    return this.leadConfigRowToDict(row, projectId);
  }

  saveProjectLeadConfig(
    projectId: number,
    payload: SaveProjectLeadConfigBody,
    updatedBy = '',
  ): ReProjectLeadConfigRow {
    this.validateProjectExists(projectId);
    this.ensureProjectLeadConfigSchema();
    const ts = catalogTs();
    const existing = this.database
      .prepare('SELECT * FROM crm_re_project_lead_config WHERE project_id = ?')
      .get(projectId) as Record<string, unknown> | undefined;
    let slug = String(existing?.webhook_slug ?? '').trim();
    if (!slug) slug = this.defaultWebhookSlug(projectId);
    let verify = String(existing?.webhook_verify_token ?? '').trim();
    if (!verify) verify = randomBytes(12).toString('base64url');
    const enabled = payload.enabled === false || payload.enabled === 0 ? 0 : 1;
    const webhookEnabled = payload.webhook_enabled === false || payload.webhook_enabled === 0 ? 0 : 1;
    const autoAssign = payload.auto_assign === false || payload.auto_assign === 0 ? 0 : 1;
    const pageId = String(payload.facebook_page_id ?? existing?.facebook_page_id ?? '').trim();
    const zaloOaId = String(payload.zalo_oa_id ?? existing?.zalo_oa_id ?? '').trim();
    if (payload.webhook_slug != null) {
      const rawSlug = String(payload.webhook_slug ?? '').trim().toLowerCase();
      if (rawSlug) {
        const other = this.database
          .prepare(
            'SELECT project_id FROM crm_re_project_lead_config WHERE webhook_slug = ? AND project_id != ?',
          )
          .get(rawSlug, projectId) as { project_id: number } | undefined;
        if (other) throw new Error(`Webhook slug «${rawSlug}» đã dùng cho dự án khác.`);
        slug = rawSlug;
      }
    }
    if (payload.regenerate_verify_token) verify = randomBytes(12).toString('base64url');
    this.database
      .prepare(
        `INSERT INTO crm_re_project_lead_config (
           project_id, enabled, webhook_slug, webhook_verify_token, facebook_page_id,
           zalo_oa_id, auto_assign, webhook_enabled, updated_at, updated_by
         ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
         ON CONFLICT(project_id) DO UPDATE SET
           enabled = excluded.enabled,
           webhook_slug = excluded.webhook_slug,
           webhook_verify_token = excluded.webhook_verify_token,
           facebook_page_id = excluded.facebook_page_id,
           zalo_oa_id = excluded.zalo_oa_id,
           auto_assign = excluded.auto_assign,
           webhook_enabled = excluded.webhook_enabled,
           updated_at = excluded.updated_at,
           updated_by = excluded.updated_by`,
      )
      .run(projectId, enabled, slug, verify, pageId, zaloOaId, autoAssign, webhookEnabled, ts, String(updatedBy).slice(0, 120));
    if (Array.isArray(payload.forms)) {
      const seen = new Set<string>();
      for (const raw of payload.forms) {
        if (!raw || typeof raw !== 'object') continue;
        const formId = String((raw as Record<string, unknown>).form_id ?? '').trim();
        if (!formId || seen.has(formId)) continue;
        seen.add(formId);
        const formName = String((raw as Record<string, unknown>).form_name ?? '').trim();
        const formPageId = String((raw as Record<string, unknown>).page_id ?? pageId).trim();
        const active = (raw as Record<string, unknown>).active === false ? 0 : 1;
        this.database
          .prepare(
            `INSERT INTO crm_re_project_facebook_forms (
               project_id, page_id, form_id, form_name, active, created_at, updated_at
             ) VALUES (?, ?, ?, ?, ?, ?, ?)
             ON CONFLICT(form_id) DO UPDATE SET
               project_id = excluded.project_id,
               page_id = excluded.page_id,
               form_name = excluded.form_name,
               active = excluded.active,
               updated_at = excluded.updated_at`,
          )
          .run(projectId, formPageId, formId, formName, active, ts, ts);
      }
    }
    if (Array.isArray(payload.zalo_campaigns)) {
      const seen = new Set<string>();
      for (const raw of payload.zalo_campaigns) {
        if (!raw || typeof raw !== 'object') continue;
        const campaignId = String((raw as Record<string, unknown>).campaign_id ?? '').trim();
        if (!campaignId || seen.has(campaignId)) continue;
        seen.add(campaignId);
        const campaignName = String((raw as Record<string, unknown>).campaign_name ?? '').trim();
        const oaId = String((raw as Record<string, unknown>).oa_id ?? zaloOaId).trim();
        const active = (raw as Record<string, unknown>).active === false ? 0 : 1;
        this.database
          .prepare(
            `INSERT INTO crm_re_project_zalo_campaigns (
               project_id, oa_id, campaign_id, campaign_name, active, created_at, updated_at
             ) VALUES (?, ?, ?, ?, ?, ?, ?)
             ON CONFLICT(campaign_id) DO UPDATE SET
               project_id = excluded.project_id,
               oa_id = excluded.oa_id,
               campaign_name = excluded.campaign_name,
               active = excluded.active,
               updated_at = excluded.updated_at`,
          )
          .run(projectId, oaId, campaignId, campaignName, active, ts, ts);
      }
    }
    if (Array.isArray(payload.website_routes)) {
      const seen = new Set<string>();
      for (const raw of payload.website_routes) {
        if (!raw || typeof raw !== 'object') continue;
        const item = raw as Record<string, unknown>;
        const routeKey = String(item.route_key ?? item.utm_campaign ?? item.campaign_code ?? '').trim();
        if (!routeKey || seen.has(routeKey)) continue;
        seen.add(routeKey);
        const routeName = String(item.route_name ?? item.route_label ?? '').trim();
        const routeType = String(item.route_type ?? 'utm').trim().toLowerCase() || 'utm';
        const active = item.active === false ? 0 : 1;
        this.database
          .prepare(
            `INSERT INTO crm_re_project_website_routes (
               project_id, route_key, route_name, route_type, active, created_at, updated_at
             ) VALUES (?, ?, ?, ?, ?, ?, ?)
             ON CONFLICT(route_key) DO UPDATE SET
               project_id = excluded.project_id,
               route_name = excluded.route_name,
               route_type = excluded.route_type,
               active = excluded.active,
               updated_at = excluded.updated_at`,
          )
          .run(projectId, routeKey, routeName, routeType, active, ts, ts);
      }
    }
    return this.getProjectLeadConfig(projectId);
  }

  computeProjectWorkflow(projectId: number): Record<string, unknown> {
    const proj = this.fetchProject(projectId);
    if (!proj) throw new Error('Không tìm thấy dự án.');
    const summary = this.fetchProjectSummary(projectId);
    return computeProjectWorkflow(projectId, proj, summary);
  }

  fetchProjectExportData(projectId: number): {
    project: ReProjectRow;
    summary: Record<string, unknown>;
    workflow: Record<string, unknown>;
    kpis: Array<Record<string, unknown>>;
    products: Array<Record<string, unknown>>;
    risks: Array<Record<string, unknown>>;
    budget: Array<Record<string, unknown>>;
  } {
    const proj = this.fetchProject(projectId);
    if (!proj) throw new Error('Không tìm thấy dự án.');
    return {
      project: proj,
      summary: this.fetchProjectSummary(projectId),
      workflow: this.computeProjectWorkflow(projectId),
      kpis: this.listKpis(projectId),
      products: this.listProducts(projectId),
      risks: this.listRisks(projectId),
      budget: this.listBudgetLines(projectId),
    };
  }
}
