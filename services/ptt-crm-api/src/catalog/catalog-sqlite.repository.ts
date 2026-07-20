import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { DatabaseSync } from 'node:sqlite';
import { AppConfigService } from '../config/app-config.service';
import { catalogTs, normalizeCatalogSlug, validateCatalogSlug } from './catalog-slug.util';
import { industryTraitsFieldCount, normalizeIndustryTraits } from './catalog-traits.util';
import {
  AssignScopeRow,
  CatalogIndustryRow,
  CatalogPublicPayload,
  CatalogServiceRow,
  CreateAssignScopeBody,
  CreateCatalogIndustryBody,
  CreateCatalogServiceBody,
  PatchAssignScopeBody,
  PatchCatalogIndustryBody,
  PatchCatalogServiceBody,
  StaffOption,
} from './catalog.types';

const WILDCARD = '*';

const DEFAULT_INDUSTRIES = [
  { slug: 'spa', name: 'Spa & Beauty', description: 'Spa, thẩm mỹ, wellness' },
  { slug: 'bds', name: 'Bất động sản', description: 'BĐS, dự án, môi giới' },
  { slug: 'giao-duc', name: 'Giáo dục', description: 'Trường, trung tâm, EdTech' },
  { slug: 'fnb', name: 'F&B', description: 'Nhà hàng, cafe, F&B chain' },
  { slug: 'khac', name: 'Khác', description: 'Ngành khác / chưa phân loại' },
];

interface ServiceDbRow {
  id: number;
  slug: string;
  name: string;
  description: string;
  sort_order: number;
  active: number;
  created_at: string;
  updated_at: string;
}

interface IndustryDbRow extends ServiceDbRow {
  traits_json: string;
}

interface ScopeDbRow {
  id: number;
  staff_id: number;
  industry_slug: string;
  service_slug: string;
  active: number;
  created_at: string;
  updated_at: string;
  staff_name?: string;
}

@Injectable()
export class CatalogSqliteRepository implements OnModuleDestroy {
  private db: DatabaseSync | null = null;

  constructor(private readonly config: AppConfigService) {}

  private get database(): DatabaseSync {
    if (!this.db) {
      this.db = new DatabaseSync(this.config.sqlitePath);
      this.db.exec('PRAGMA foreign_keys = ON');
      this.ensureSchema(this.db);
    }
    return this.db;
  }

  onModuleDestroy(): void {
    if (this.db) {
      this.db.close();
      this.db = null;
    }
  }

  private ensureSchema(db: DatabaseSync): void {
    db.exec(`
      CREATE TABLE IF NOT EXISTS crm_catalog_services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL DEFAULT '',
        description TEXT NOT NULL DEFAULT '',
        sort_order INTEGER NOT NULL DEFAULT 0,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL DEFAULT ''
      );
      CREATE TABLE IF NOT EXISTS crm_catalog_industries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL DEFAULT '',
        description TEXT NOT NULL DEFAULT '',
        traits_json TEXT NOT NULL DEFAULT '{}',
        sort_order INTEGER NOT NULL DEFAULT 0,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL DEFAULT ''
      );
      CREATE TABLE IF NOT EXISTS crm_staff_assign_scope (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_id INTEGER NOT NULL,
        industry_slug TEXT NOT NULL DEFAULT '*',
        service_slug TEXT NOT NULL DEFAULT '*',
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL DEFAULT ''
      );
    `);
    this.bootstrapIfEmpty(db);
  }

  private bootstrapIfEmpty(db: DatabaseSync): void {
    const svcCount = db.prepare('SELECT COUNT(*) AS c FROM crm_catalog_services').get() as { c: number };
    if (Number(svcCount?.c ?? 0) === 0) {
      const ts = catalogTs();
      db.prepare(
        `INSERT OR IGNORE INTO crm_catalog_services
         (slug, name, description, sort_order, active, created_at, updated_at)
         VALUES (?, ?, '', ?, 1, ?, ?)`,
      ).run('lead-gen', 'Lead generation', 10, ts, ts);
    }
    const indCount = db.prepare('SELECT COUNT(*) AS c FROM crm_catalog_industries').get() as { c: number };
    if (Number(indCount?.c ?? 0) === 0) {
      const ts = catalogTs();
      DEFAULT_INDUSTRIES.forEach((item, i) => {
        db.prepare(
          `INSERT OR IGNORE INTO crm_catalog_industries
           (slug, name, description, traits_json, sort_order, active, created_at, updated_at)
           VALUES (?, ?, ?, '{}', ?, 1, ?, ?)`,
        ).run(item.slug, item.name, item.description, (i + 1) * 10, ts, ts);
      });
    }
  }

  private mapService(row: ServiceDbRow): CatalogServiceRow {
    return {
      id: Number(row.id),
      slug: String(row.slug ?? ''),
      name: String(row.name ?? ''),
      description: String(row.description ?? ''),
      sort_order: Number(row.sort_order ?? 0),
      active: Boolean(Number(row.active ?? 0)),
      created_at: String(row.created_at ?? ''),
      updated_at: String(row.updated_at ?? ''),
    };
  }

  private mapIndustry(row: IndustryDbRow): CatalogIndustryRow {
    let traits: Record<string, unknown> = {};
    try {
      traits = JSON.parse(String(row.traits_json ?? '{}')) as Record<string, unknown>;
    } catch {
      traits = {};
    }
    return {
      id: Number(row.id),
      slug: String(row.slug ?? ''),
      name: String(row.name ?? ''),
      description: String(row.description ?? ''),
      traits: typeof traits === 'object' && traits !== null ? traits : {},
      sort_order: Number(row.sort_order ?? 0),
      active: Boolean(Number(row.active ?? 0)),
      created_at: String(row.created_at ?? ''),
      updated_at: String(row.updated_at ?? ''),
    };
  }

  private mapScope(row: ScopeDbRow): AssignScopeRow {
    return {
      id: Number(row.id),
      staff_id: Number(row.staff_id),
      industry_slug: String(row.industry_slug ?? WILDCARD),
      service_slug: String(row.service_slug ?? WILDCARD),
      active: Boolean(Number(row.active ?? 0)),
      created_at: String(row.created_at ?? ''),
      updated_at: String(row.updated_at ?? ''),
      staff_name: String(row.staff_name ?? ''),
    };
  }

  private normScopeSlug(raw: string | undefined): string {
    if (!raw || raw.trim() === '' || raw === WILDCARD) return WILDCARD;
    return normalizeCatalogSlug(raw) || WILDCARD;
  }

  listServices(activeOnly = false): CatalogServiceRow[] {
    const sql = activeOnly
      ? `SELECT * FROM crm_catalog_services WHERE active = 1 ORDER BY sort_order ASC, name ASC, id ASC`
      : `SELECT * FROM crm_catalog_services ORDER BY sort_order ASC, name ASC, id ASC`;
    const rows = this.database.prepare(sql).all() as unknown as ServiceDbRow[];
    return rows.map((r) => this.mapService(r));
  }

  listIndustries(activeOnly = false): CatalogIndustryRow[] {
    const sql = activeOnly
      ? `SELECT * FROM crm_catalog_industries WHERE active = 1 ORDER BY sort_order ASC, name ASC, id ASC`
      : `SELECT * FROM crm_catalog_industries ORDER BY sort_order ASC, name ASC, id ASC`;
    const rows = this.database.prepare(sql).all() as unknown as IndustryDbRow[];
    return rows.map((r) => this.mapIndustry(r));
  }

  publicPayload(): CatalogPublicPayload {
    const services = this.listServices(true);
    const industries = this.listIndustries(true);
    return {
      services,
      industries,
      service_slugs: services.map((s) => s.slug),
      service_labels: Object.fromEntries(services.map((s) => [s.slug, s.name])),
      industry_slugs: industries.map((i) => i.slug),
      industry_labels: Object.fromEntries(industries.map((i) => [i.slug, i.name])),
    };
  }

  createService(body: CreateCatalogServiceBody): CatalogServiceRow {
    const key = validateCatalogSlug(body.slug);
    const name = String(body.name ?? '').trim();
    if (!name) throw new Error('Tên dịch vụ bắt buộc.');
    const dup = this.database.prepare('SELECT id FROM crm_catalog_services WHERE slug = ?').get(key);
    if (dup) throw new Error(`Slug dịch vụ đã tồn tại: ${key}`);
    const ts = catalogTs();
    const result = this.database
      .prepare(
        `INSERT INTO crm_catalog_services
         (slug, name, description, sort_order, active, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        key,
        name.slice(0, 200),
        String(body.description ?? '').trim().slice(0, 500),
        Number(body.sort_order ?? 0),
        body.active === false ? 0 : 1,
        ts,
        ts,
      );
    const row = this.database
      .prepare('SELECT * FROM crm_catalog_services WHERE id = ?')
      .get(Number(result.lastInsertRowid)) as unknown as ServiceDbRow;
    return this.mapService(row);
  }

  updateService(id: number, body: PatchCatalogServiceBody): CatalogServiceRow {
    const row = this.database.prepare('SELECT * FROM crm_catalog_services WHERE id = ?').get(id) as
      | ServiceDbRow
      | undefined;
    if (!row) throw new Error('Không tìm thấy dịch vụ.');
    const name = String(body.name ?? row.name).trim();
    if (!name) throw new Error('Tên dịch vụ bắt buộc.');
    const ts = catalogTs();
    this.database
      .prepare(
        `UPDATE crm_catalog_services
         SET name = ?, description = ?, sort_order = ?, active = ?, updated_at = ?
         WHERE id = ?`,
      )
      .run(
        name.slice(0, 200),
        String(body.description ?? row.description).trim().slice(0, 500),
        body.sort_order !== undefined ? Number(body.sort_order) : Number(row.sort_order),
        body.active !== undefined ? (body.active ? 1 : 0) : Number(row.active),
        ts,
        id,
      );
    const out = this.database.prepare('SELECT * FROM crm_catalog_services WHERE id = ?').get(id) as unknown as ServiceDbRow;
    return this.mapService(out);
  }

  createIndustry(body: CreateCatalogIndustryBody): CatalogIndustryRow {
    const key = validateCatalogSlug(body.slug);
    const name = String(body.name ?? '').trim();
    if (!name) throw new Error('Tên ngành bắt buộc.');
    const dup = this.database.prepare('SELECT id FROM crm_catalog_industries WHERE slug = ?').get(key);
    if (dup) throw new Error(`Slug ngành đã tồn tại: ${key}`);
    const ts = catalogTs();
    const result = this.database
      .prepare(
        `INSERT INTO crm_catalog_industries
         (slug, name, description, traits_json, sort_order, active, created_at, updated_at)
         VALUES (?, ?, ?, '{}', ?, ?, ?, ?)`,
      )
      .run(
        key,
        name.slice(0, 200),
        String(body.description ?? '').trim().slice(0, 500),
        Number(body.sort_order ?? 0),
        body.active === false ? 0 : 1,
        ts,
        ts,
      );
    const row = this.database
      .prepare('SELECT * FROM crm_catalog_industries WHERE id = ?')
      .get(Number(result.lastInsertRowid)) as unknown as IndustryDbRow;
    return this.mapIndustry(row);
  }

  updateIndustry(id: number, body: PatchCatalogIndustryBody): CatalogIndustryRow {
    const row = this.database.prepare('SELECT * FROM crm_catalog_industries WHERE id = ?').get(id) as
      | IndustryDbRow
      | undefined;
    if (!row) throw new Error('Không tìm thấy ngành.');
    const name = String(body.name ?? row.name).trim();
    if (!name) throw new Error('Tên ngành bắt buộc.');
    const ts = catalogTs();
    const sets = ['name = ?', 'description = ?', 'sort_order = ?', 'active = ?', 'updated_at = ?'];
    const params: Array<string | number> = [
      name.slice(0, 200),
      String(body.description ?? row.description).trim().slice(0, 500),
      body.sort_order !== undefined ? Number(body.sort_order) : Number(row.sort_order),
      body.active !== undefined ? (body.active ? 1 : 0) : Number(row.active),
      ts,
    ];
    if (body.traits !== undefined) {
      const norm = normalizeIndustryTraits(body.traits);
      sets.push('traits_json = ?');
      params.push(JSON.stringify(norm));
    }
    params.push(id);
    this.database.prepare(`UPDATE crm_catalog_industries SET ${sets.join(', ')} WHERE id = ?`).run(...params);
    const out = this.database.prepare('SELECT * FROM crm_catalog_industries WHERE id = ?').get(id) as unknown as IndustryDbRow;
    return this.mapIndustry(out);
  }

  listAssignScopes(): { scopes: AssignScopeRow[]; staff: StaffOption[] } {
    let scopes: AssignScopeRow[] = [];
    try {
      const rows = this.database
        .prepare(
          `SELECT sc.*, s.name AS staff_name
           FROM crm_staff_assign_scope sc
           JOIN crm_staff s ON s.id = sc.staff_id
           ORDER BY s.name ASC, sc.industry_slug ASC, sc.service_slug ASC, sc.id ASC`,
        )
        .all() as unknown as ScopeDbRow[];
      scopes = rows.map((r) => this.mapScope(r));
    } catch {
      scopes = [];
    }
    let staff: StaffOption[] = [];
    try {
      const staffRows = this.database
        .prepare(
          `SELECT id, name, internal_code FROM crm_staff
           WHERE COALESCE(active, 1) = 1 ORDER BY name ASC, id ASC`,
        )
        .all() as Array<{ id: number; name: string; internal_code: string }>;
      staff = staffRows.map((r) => ({
        id: Number(r.id),
        name: String(r.name ?? ''),
        internal_code: String(r.internal_code ?? ''),
      }));
    } catch {
      staff = [];
    }
    return { scopes, staff };
  }

  createAssignScope(body: CreateAssignScopeBody): AssignScopeRow {
    const staffId = Number(body.staff_id);
    if (!staffId) throw new Error('Nhân viên không hợp lệ.');
    const staff = this.database
      .prepare('SELECT id FROM crm_staff WHERE id = ? AND COALESCE(active, 1) = 1')
      .get(staffId);
    if (!staff) throw new Error('Nhân viên không hợp lệ.');
    const ind = this.normScopeSlug(body.industry_slug);
    const svc = this.normScopeSlug(body.service_slug);
    if (ind !== WILDCARD) this.validateIndustrySlug(ind);
    if (svc !== WILDCARD) this.validateServiceSlug(svc);
    const dup = this.database
      .prepare(
        `SELECT id FROM crm_staff_assign_scope WHERE staff_id = ? AND industry_slug = ? AND service_slug = ?`,
      )
      .get(staffId, ind, svc);
    if (dup) throw new Error('Phạm vi phân lead đã tồn tại cho AM này.');
    const ts = catalogTs();
    const result = this.database
      .prepare(
        `INSERT INTO crm_staff_assign_scope
         (staff_id, industry_slug, service_slug, active, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?)`,
      )
      .run(staffId, ind, svc, body.active === false ? 0 : 1, ts, ts);
    const row = this.database
      .prepare(
        `SELECT sc.*, s.name AS staff_name FROM crm_staff_assign_scope sc
         JOIN crm_staff s ON s.id = sc.staff_id WHERE sc.id = ?`,
      )
      .get(Number(result.lastInsertRowid)) as unknown as ScopeDbRow;
    return this.mapScope(row);
  }

  updateAssignScope(id: number, body: PatchAssignScopeBody): AssignScopeRow {
    const row = this.database.prepare('SELECT * FROM crm_staff_assign_scope WHERE id = ?').get(id);
    if (!row) throw new Error('Không tìm thấy phạm vi phân lead.');
    const ts = catalogTs();
    const active =
      body.active !== undefined ? (body.active ? 1 : 0) : Number((row as unknown as ScopeDbRow).active ?? 0);
    this.database
      .prepare('UPDATE crm_staff_assign_scope SET active = ?, updated_at = ? WHERE id = ?')
      .run(active, ts, id);
    const out = this.database
      .prepare(
        `SELECT sc.*, s.name AS staff_name FROM crm_staff_assign_scope sc
         JOIN crm_staff s ON s.id = sc.staff_id WHERE sc.id = ?`,
      )
      .get(id) as unknown as ScopeDbRow;
    return this.mapScope(out);
  }

  deleteAssignScope(id: number): void {
    const result = this.database.prepare('DELETE FROM crm_staff_assign_scope WHERE id = ?').run(id);
    if (Number(result.changes ?? 0) === 0) throw new Error('Không tìm thấy phạm vi phân lead.');
  }

  private validateServiceSlug(slug: string): void {
    const row = this.database
      .prepare('SELECT 1 FROM crm_catalog_services WHERE slug = ? AND active = 1 LIMIT 1')
      .get(slug);
    if (!row) throw new Error(`Dịch vụ không hợp lệ hoặc đã vô hiệu: ${slug}`);
  }

  private validateIndustrySlug(slug: string): void {
    const row = this.database
      .prepare('SELECT 1 FROM crm_catalog_industries WHERE slug = ? AND active = 1 LIMIT 1')
      .get(slug);
    if (!row) throw new Error(`Ngành không hợp lệ hoặc đã vô hiệu: ${slug}`);
  }

  industryAddonCount(traits: Record<string, unknown> | undefined): number {
    return industryTraitsFieldCount(traits);
  }
}
