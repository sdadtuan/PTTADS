import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { DatabaseSync } from 'node:sqlite';
import { catalogTs } from '../catalog/catalog-slug.util';
import { AppConfigService } from '../config/app-config.service';

@Injectable()
export class ReProjectsAccountingRepository implements OnModuleDestroy {
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

  ensureAccountingSchema(): void {
    this.database.exec(`
      CREATE TABLE IF NOT EXISTS crm_re_project_cash_flow_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL REFERENCES crm_re_projects(id) ON DELETE CASCADE,
        flow_type TEXT NOT NULL DEFAULT 'outflow',
        category TEXT NOT NULL DEFAULT 'other',
        sub_category TEXT NOT NULL DEFAULT '',
        line_item TEXT NOT NULL DEFAULT '',
        amount_vnd INTEGER NOT NULL DEFAULT 0,
        period_month TEXT NOT NULL DEFAULT '',
        transaction_date TEXT NOT NULL DEFAULT '',
        due_date TEXT NOT NULL DEFAULT '',
        paid_date TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'planned',
        source_type TEXT NOT NULL DEFAULT 'manual',
        source_ref TEXT NOT NULL DEFAULT '',
        counterparty TEXT NOT NULL DEFAULT '',
        notes TEXT NOT NULL DEFAULT '',
        created_by TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
      )
    `);
    this.database.exec(
      'CREATE INDEX IF NOT EXISTS idx_crm_re_cash_flow_project ' +
        'ON crm_re_project_cash_flow_lines(project_id, period_month, status)',
    );
    this.database.exec(
      'CREATE INDEX IF NOT EXISTS idx_crm_re_cash_flow_category ' +
        'ON crm_re_project_cash_flow_lines(project_id, category, flow_type)',
    );
    if (this.tableExists('crm_re_project_budget_lines')) {
      const cols = this.database.prepare('PRAGMA table_info(crm_re_project_budget_lines)').all() as Array<{
        name: string;
      }>;
      const colSet = new Set(cols.map((c) => c.name));
      for (const [col, ddl] of [
        ['sub_category', "TEXT NOT NULL DEFAULT ''"],
        ['source_type', "TEXT NOT NULL DEFAULT 'manual'"],
        ['source_ref', "TEXT NOT NULL DEFAULT ''"],
      ] as const) {
        if (!colSet.has(col)) {
          this.database.exec(`ALTER TABLE crm_re_project_budget_lines ADD COLUMN ${col} ${ddl}`);
        }
      }
    }
  }

  queryCashFlowRows(
    projectId: number,
    whereExtra: string,
    params: Array<string | number>,
  ): Array<Record<string, unknown>> {
    this.ensureAccountingSchema();
    return this.database
      .prepare(
        `SELECT * FROM crm_re_project_cash_flow_lines WHERE project_id = ? ${whereExtra} ` +
          "ORDER BY COALESCE(NULLIF(transaction_date,''), period_month) DESC, id DESC",
      )
      .all(projectId, ...params) as Array<Record<string, unknown>>;
  }

  getCashFlowRow(lineId: number): Record<string, unknown> | undefined {
    this.ensureAccountingSchema();
    return this.database
      .prepare('SELECT * FROM crm_re_project_cash_flow_lines WHERE id = ?')
      .get(lineId) as Record<string, unknown> | undefined;
  }

  insertCashFlowLine(projectId: number, fields: Array<string | number>, ts: string): number {
    this.ensureAccountingSchema();
    const result = this.database
      .prepare(
        `INSERT INTO crm_re_project_cash_flow_lines (
           project_id, flow_type, category, sub_category, line_item, amount_vnd,
           period_month, transaction_date, due_date, paid_date, status,
           source_type, source_ref, counterparty, notes, created_by, created_at, updated_at
         ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(projectId, ...fields, ts, ts);
    return Number(result.lastInsertRowid);
  }

  updateCashFlowLine(
    projectId: number,
    lineId: number,
    fields: Array<string | number>,
    ts: string,
  ): void {
    this.ensureAccountingSchema();
    this.database
      .prepare(
        `UPDATE crm_re_project_cash_flow_lines SET
           flow_type=?, category=?, sub_category=?, line_item=?, amount_vnd=?,
           period_month=?, transaction_date=?, due_date=?, paid_date=?,
           status=?, source_type=?, source_ref=?, counterparty=?, notes=?, updated_at=?
         WHERE id=? AND project_id=?`,
      )
      .run(...fields, ts, lineId, projectId);
  }

  deleteCashFlowLine(projectId: number, lineId: number): void {
    this.ensureAccountingSchema();
    this.database
      .prepare('DELETE FROM crm_re_project_cash_flow_lines WHERE id = ? AND project_id = ?')
      .run(lineId, projectId);
  }

  findCashFlowBySourceRef(projectId: number, sourceRef: string): { id: number } | undefined {
    this.ensureAccountingSchema();
    return this.database
      .prepare('SELECT id FROM crm_re_project_cash_flow_lines WHERE project_id = ? AND source_ref = ?')
      .get(projectId, sourceRef) as { id: number } | undefined;
  }

  findBudgetBySourceRef(projectId: number, sourceRef: string): { id: number; planned_vnd: number } | undefined {
    if (!this.tableExists('crm_re_project_budget_lines')) return undefined;
    this.ensureAccountingSchema();
    return this.database
      .prepare('SELECT id, planned_vnd FROM crm_re_project_budget_lines WHERE project_id = ? AND source_ref = ?')
      .get(projectId, sourceRef) as { id: number; planned_vnd: number } | undefined;
  }

  upsertBudgetByRef(
    projectId: number,
    data: {
      category: string;
      lineItem: string;
      plannedVnd: number;
      sourceRef: string;
      sourceType?: string;
      subCategory?: string;
    },
    ts: string,
  ): ['created' | 'updated' | 'skipped', number] {
    if (!this.tableExists('crm_re_project_budget_lines')) return ['skipped', 0];
    this.ensureAccountingSchema();
    const ref = String(data.sourceRef ?? '').trim();
    if (!ref) return ['skipped', 0];
    const existing = this.findBudgetBySourceRef(projectId, ref);
    if (existing) {
      if (Number(existing.planned_vnd ?? 0) === Number(data.plannedVnd)) {
        return ['skipped', Number(existing.id)];
      }
      this.database
        .prepare(
          `UPDATE crm_re_project_budget_lines
           SET category=?, line_item=?, planned_vnd=?, source_type=?, sub_category=?, updated_at=?
           WHERE id=? AND project_id=?`,
        )
        .run(
          data.category,
          data.lineItem.slice(0, 200),
          Number(data.plannedVnd),
          data.sourceType ?? 'plan_sync',
          (data.subCategory ?? '').slice(0, 40),
          ts,
          existing.id,
          projectId,
        );
      return ['updated', Number(existing.id)];
    }
    const result = this.database
      .prepare(
        `INSERT INTO crm_re_project_budget_lines (
           project_id, category, line_item, period_month, planned_vnd, actual_vnd,
           notes, sub_category, source_type, source_ref, created_at, updated_at
         ) VALUES (?, ?, ?, '', ?, 0, '', ?, ?, ?, ?, ?)`,
      )
      .run(
        projectId,
        data.category,
        data.lineItem.slice(0, 200),
        Number(data.plannedVnd),
        (data.subCategory ?? '').slice(0, 40),
        data.sourceType ?? 'plan_sync',
        ref,
        ts,
        ts,
      );
    return ['created', Number(result.lastInsertRowid)];
  }

  updateBudgetActual(
    projectId: number,
    budgetId: number,
    actualVnd: number,
    lineItem: string,
    ts: string,
  ): void {
    if (!this.tableExists('crm_re_project_budget_lines')) return;
    this.database
      .prepare(
        `UPDATE crm_re_project_budget_lines
         SET actual_vnd=?, line_item=?, updated_at=?
         WHERE id=? AND project_id=?`,
      )
      .run(actualVnd, lineItem.slice(0, 200), ts, budgetId, projectId);
  }

  insertInventoryBudgetLine(
    projectId: number,
    lineItem: string,
    period: string,
    actualVnd: number,
    ts: string,
  ): void {
    if (!this.tableExists('crm_re_project_budget_lines')) return;
    this.ensureAccountingSchema();
    this.database
      .prepare(
        `INSERT INTO crm_re_project_budget_lines (
           project_id, category, line_item, period_month, planned_vnd, actual_vnd,
           notes, sub_category, source_type, source_ref, created_at, updated_at
         ) VALUES (?, 'revenue', ?, ?, 0, ?, '', '', 'inventory', 'inventory:revenue', ?, ?)`,
      )
      .run(projectId, lineItem.slice(0, 200), period, actualVnd, ts, ts);
  }

  nowTs(): string {
    return catalogTs();
  }
}
