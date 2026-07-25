import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { DatabaseSync } from 'node:sqlite';
import { AppConfigService } from '../config/app-config.service';

export interface LifecycleFinanceConfirmRow {
  id: number;
  lifecycle_id: number;
  staff_id: number | null;
  staff_email: string;
  outstanding_vnd: number;
  ar_pending_vnd: number;
  ar_overdue_vnd: number;
  strict_mode: boolean;
  note: string | null;
  created_at: string;
}

@Injectable()
export class LifecycleFinanceConfirmRepository implements OnModuleDestroy {
  private db: DatabaseSync | null = null;

  constructor(private readonly config: AppConfigService) {}

  private get database(): DatabaseSync {
    if (!this.db) {
      this.db = new DatabaseSync(this.config.sqlitePath);
      this.db.exec('PRAGMA foreign_keys = ON');
      this.ensureTable();
    }
    return this.db;
  }

  onModuleDestroy(): void {
    if (this.db) {
      this.db.close();
      this.db = null;
    }
  }

  private ensureTable(): void {
    this.db!.exec(`
      CREATE TABLE IF NOT EXISTS lifecycle_finance_confirm (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lifecycle_id INTEGER NOT NULL,
        staff_id INTEGER,
        staff_email TEXT NOT NULL DEFAULT '',
        outstanding_vnd INTEGER NOT NULL DEFAULT 0,
        ar_pending_vnd INTEGER NOT NULL DEFAULT 0,
        ar_overdue_vnd INTEGER NOT NULL DEFAULT 0,
        strict_mode INTEGER NOT NULL DEFAULT 0,
        note TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
      );
      CREATE INDEX IF NOT EXISTS idx_lifecycle_finance_confirm_lc
        ON lifecycle_finance_confirm (lifecycle_id, created_at DESC);
    `);
  }

  insertConfirm(input: {
    lifecycleId: number;
    staffId?: number | null;
    staffEmail: string;
    outstandingVnd: number;
    arPendingVnd: number;
    arOverdueVnd: number;
    strictMode: boolean;
    note?: string | null;
  }): LifecycleFinanceConfirmRow {
    const result = this.database
      .prepare(
        `INSERT INTO lifecycle_finance_confirm
         (lifecycle_id, staff_id, staff_email, outstanding_vnd, ar_pending_vnd, ar_overdue_vnd, strict_mode, note)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        input.lifecycleId,
        input.staffId ?? null,
        input.staffEmail,
        input.outstandingVnd,
        input.arPendingVnd,
        input.arOverdueVnd,
        input.strictMode ? 1 : 0,
        input.note ?? null,
      );
    const row = this.database
      .prepare(`SELECT * FROM lifecycle_finance_confirm WHERE id = ?`)
      .get(Number(result.lastInsertRowid)) as Record<string, unknown>;
    return this.mapRow(row);
  }

  listForLifecycle(lifecycleId: number, limit = 20): LifecycleFinanceConfirmRow[] {
    const rows = this.database
      .prepare(
        `SELECT * FROM lifecycle_finance_confirm
         WHERE lifecycle_id = ?
         ORDER BY created_at DESC, id DESC
         LIMIT ?`,
      )
      .all(lifecycleId, limit) as Array<Record<string, unknown>>;
    return rows.map((row) => this.mapRow(row));
  }

  private mapRow(row: Record<string, unknown>): LifecycleFinanceConfirmRow {
    return {
      id: Number(row.id),
      lifecycle_id: Number(row.lifecycle_id),
      staff_id: row.staff_id != null ? Number(row.staff_id) : null,
      staff_email: String(row.staff_email ?? ''),
      outstanding_vnd: Number(row.outstanding_vnd ?? 0),
      ar_pending_vnd: Number(row.ar_pending_vnd ?? 0),
      ar_overdue_vnd: Number(row.ar_overdue_vnd ?? 0),
      strict_mode: Boolean(row.strict_mode),
      note: row.note != null ? String(row.note) : null,
      created_at: String(row.created_at ?? ''),
    };
  }
}
