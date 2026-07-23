import type { DatabaseSync } from 'node:sqlite';
import { catalogTs } from '../catalog/catalog-slug.util';

/** Link presales expenses to lifecycle after promote — parity crm_svc_finance.link_presales_expenses_to_lifecycle */
export function linkPresalesExpensesToLifecycle(
  db: DatabaseSync,
  presalesId: number,
  lifecycleId: number,
): number {
  const ts = catalogTs();
  const result = db
    .prepare(
      `UPDATE crm_svc_expenses
       SET lifecycle_id = ?, updated_at = ?
       WHERE presales_id = ? AND cost_phase = 'presales' AND lifecycle_id IS NULL`,
    )
    .run(lifecycleId, ts, presalesId);
  return Number(result.changes ?? 0);
}

export function ensureSvcExpensesSchema(db: DatabaseSync): void {
  db.exec(`
    CREATE TABLE IF NOT EXISTS crm_svc_expenses (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      lifecycle_id INTEGER,
      presales_id INTEGER,
      lead_id INTEGER,
      title TEXT NOT NULL DEFAULT '',
      category TEXT NOT NULL DEFAULT '',
      amount_vnd INTEGER NOT NULL DEFAULT 0,
      expense_on TEXT NOT NULL DEFAULT '',
      notes TEXT NOT NULL DEFAULT '',
      cost_phase TEXT NOT NULL DEFAULT 'delivery',
      stage TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL DEFAULT '',
      updated_at TEXT NOT NULL DEFAULT ''
    )
  `);
}

export function createLifecycleExpense(
  db: DatabaseSync,
  lifecycleId: number,
  body: { title?: string; category?: string; amount_vnd?: number; expense_on?: string; notes?: string },
): Record<string, unknown> {
  ensureSvcExpensesSchema(db);
  const ts = catalogTs();
  const title = String(body.title ?? '').trim().slice(0, 240);
  const category = String(body.category ?? 'khac').trim().slice(0, 80);
  const amountVnd = Math.max(0, Number(body.amount_vnd ?? 0));
  const expenseOn = String(body.expense_on ?? ts.slice(0, 10)).slice(0, 10);
  const notes = String(body.notes ?? '').trim().slice(0, 2000);
  const id = Number(
    db
      .prepare(
        `INSERT INTO crm_svc_expenses
           (lifecycle_id, title, category, amount_vnd, expense_on, notes, cost_phase, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, 'delivery', ?, ?)`,
      )
      .run(lifecycleId, title, category, amountVnd, expenseOn, notes, ts, ts).lastInsertRowid,
  );
  return { id, lifecycle_id: lifecycleId, title, category, amount_vnd: amountVnd, expense_on: expenseOn, notes };
}

export function listPresalesSummary(db: DatabaseSync, lifecycleId: number): Record<string, unknown> {
  ensureSvcExpensesSchema(db);
  const rows = db
    .prepare(
      `SELECT id, title, category, amount_vnd, expense_on, cost_phase, notes
       FROM crm_svc_expenses WHERE lifecycle_id = ? ORDER BY expense_on DESC, id DESC`,
    )
    .all(lifecycleId) as Array<Record<string, unknown>>;
  const presales = rows.filter((r) => String(r.cost_phase) === 'presales');
  const delivery = rows.filter((r) => String(r.cost_phase) !== 'presales');
  const sum = (arr: Array<Record<string, unknown>>) =>
    arr.reduce((acc, r) => acc + Number(r.amount_vnd ?? 0), 0);
  return {
    lifecycle_id: lifecycleId,
    presales_expenses: presales,
    delivery_expenses: delivery,
    presales_total_vnd: sum(presales),
    delivery_total_vnd: sum(delivery),
  };
}
