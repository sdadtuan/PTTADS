import { DatabaseSync, type SQLInputValue } from 'node:sqlite';
import {
  COST_PHASE_DELIVERY,
  COST_PHASE_PRESALES,
  getSummary as getFinanceSummary,
} from '../finance/finance-metrics.util';

export { getFinanceSummary as getSummary };

export const VALID_COST_PHASES = new Set([COST_PHASE_DELIVERY, COST_PHASE_PRESALES]);

export const PRESALES_CATEGORIES = new Set([
  'dien_thoai',
  'di_lai',
  'cong_lead',
  'cong_tu_van',
  'cong_cu',
  'khac_presales',
]);

export const PRESALES_LIFECYCLE_STAGES = new Set(['lead', 'consult', 'proposal']);

export class ExpenseValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ExpenseValidationError';
  }
}

function ts(): string {
  return new Date().toISOString().slice(0, 19).replace('T', ' ');
}

function deliveryPhaseSql(column = 'cost_phase'): string {
  return `COALESCE(NULLIF(${column}, ''), '${COST_PHASE_DELIVERY}') = '${COST_PHASE_DELIVERY}'`;
}

function getLifecycleRow(
  db: DatabaseSync,
  lifecycleId: number,
): { id: number; stage: string; status: string } | null {
  const row = db
    .prepare('SELECT id, stage, status FROM crm_service_lifecycle WHERE id = ?')
    .get(lifecycleId) as Record<string, unknown> | undefined;
  if (!row) return null;
  return {
    id: Number(row.id),
    stage: String(row.stage ?? 'lead'),
    status: String(row.status ?? 'draft'),
  };
}

export function isPresalesLifecycle(stage: string, status: string): boolean {
  const st = String(stage || 'lead');
  const stat = String(status || 'draft');
  if (stat === 'draft') return true;
  if (PRESALES_LIFECYCLE_STAGES.has(st) && stat !== 'active') return true;
  return PRESALES_LIFECYCLE_STAGES.has(st);
}

export function resolveDefaultCostPhase(
  db: DatabaseSync,
  lifecycleId: number,
): [string, string] {
  const row = getLifecycleRow(db, lifecycleId);
  if (!row) return [COST_PHASE_DELIVERY, ''];
  const stage = row.stage;
  const status = row.status;
  if (isPresalesLifecycle(stage, status)) {
    return [COST_PHASE_PRESALES, stage];
  }
  return [COST_PHASE_DELIVERY, stage];
}

export function validateExpense(
  db: DatabaseSync,
  lifecycleId: number,
  opts: {
    costPhase: string;
    lifecycleStage: string;
    category: string;
  },
): void {
  const phase = String(opts.costPhase || COST_PHASE_DELIVERY).trim();
  if (!VALID_COST_PHASES.has(phase)) {
    throw new ExpenseValidationError(`cost_phase không hợp lệ: ${phase}`);
  }
  const row = getLifecycleRow(db, lifecycleId);
  if (!row) {
    throw new ExpenseValidationError('Không tìm thấy lifecycle.');
  }
  const stage = row.stage;
  const status = row.status;
  const cat = String(opts.category || 'khac').trim();

  if (phase === COST_PHASE_PRESALES) {
    if (!isPresalesLifecycle(stage, status)) {
      throw new ExpenseValidationError(
        'Chỉ ghi chi phí pre-sales khi lifecycle ở Lead/Consult/Proposal (draft).',
      );
    }
    if (!PRESALES_CATEGORIES.has(cat)) {
      throw new ExpenseValidationError(`Category pre-sales không hợp lệ: ${cat}`);
    }
    const st = String(opts.lifecycleStage || stage).trim();
    if (st && !PRESALES_LIFECYCLE_STAGES.has(st)) {
      throw new ExpenseValidationError(`lifecycle_stage không hợp lệ: ${st}`);
    }
  } else if (PRESALES_CATEGORIES.has(cat)) {
    throw new ExpenseValidationError('Category pre-sales chỉ dùng với cost_phase=presales.');
  }
}

export function createPayment(
  db: DatabaseSync,
  lifecycleId: number,
  amountVnd: number,
  receivedOn: string,
  status = 'pending',
  notes = '',
  dueOn = '',
): number {
  const now = ts();
  const stat = String(status || 'pending').trim();
  const recv = String(receivedOn || '').trim().slice(0, 10);
  let due = String(dueOn || '').trim().slice(0, 10);
  if (stat === 'pending' && !due) {
    due = recv;
  }
  const result = db
    .prepare(
      `
      INSERT INTO crm_svc_payments
        (lifecycle_id, amount_vnd, received_on, due_on, status, notes, created_at, updated_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `,
    )
    .run(lifecycleId, amountVnd, recv, due, stat, notes, now, now);
  return Number(result.lastInsertRowid);
}

export function updatePayment(
  db: DatabaseSync,
  paymentId: number,
  patch: {
    amountVnd?: number;
    receivedOn?: string;
    dueOn?: string;
    status?: string;
    notes?: string;
  },
): void {
  const now = ts();
  const sets = ['updated_at = ?'];
  const params: SQLInputValue[] = [now];
  if (patch.amountVnd != null) {
    sets.push('amount_vnd = ?');
    params.push(patch.amountVnd);
  }
  if (patch.receivedOn != null) {
    sets.push('received_on = ?');
    params.push(String(patch.receivedOn).trim().slice(0, 10));
  }
  if (patch.dueOn != null) {
    sets.push('due_on = ?');
    params.push(String(patch.dueOn).trim().slice(0, 10));
  }
  if (patch.status != null) {
    sets.push('status = ?');
    params.push(String(patch.status).trim());
  }
  if (patch.notes != null) {
    sets.push('notes = ?');
    params.push(patch.notes);
  }
  params.push(paymentId);
  db.prepare(`UPDATE crm_svc_payments SET ${sets.join(', ')} WHERE id = ?`).run(...params);
}

export function deletePayment(db: DatabaseSync, paymentId: number): boolean {
  const result = db.prepare('DELETE FROM crm_svc_payments WHERE id = ?').run(paymentId);
  return result.changes > 0;
}

export function createExpense(
  db: DatabaseSync,
  lifecycleId: number,
  title: string,
  category: string,
  amountVnd: number,
  expenseOn: string,
  notes = '',
  opts: { costPhase?: string | null; lifecycleStage?: string | null } = {},
): number {
  let costPhase = opts.costPhase;
  let lifecycleStage = opts.lifecycleStage;
  if (costPhase == null) {
    const [phase, autoStage] = resolveDefaultCostPhase(db, lifecycleId);
    costPhase = phase;
    if (!lifecycleStage) {
      lifecycleStage = autoStage;
    }
  }
  const phase = String(costPhase || COST_PHASE_DELIVERY).trim();
  const stage = String(lifecycleStage || '').trim();
  validateExpense(db, lifecycleId, {
    costPhase: phase,
    lifecycleStage: stage,
    category,
  });
  const now = ts();
  const result = db
    .prepare(
      `
      INSERT INTO crm_svc_expenses
        (lifecycle_id, lead_id, presales_id, title, category, amount_vnd, expense_on, notes,
         cost_phase, lifecycle_stage, created_at, updated_at)
      VALUES (?, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `,
    )
    .run(
      lifecycleId,
      title,
      category,
      amountVnd,
      String(expenseOn || '').trim().slice(0, 10),
      notes,
      phase,
      stage,
      now,
      now,
    );
  return Number(result.lastInsertRowid);
}

export function updateExpense(
  db: DatabaseSync,
  expenseId: number,
  patch: {
    title?: string;
    category?: string;
    amountVnd?: number;
    expenseOn?: string;
    notes?: string;
  },
): void {
  const now = ts();
  const sets = ['updated_at = ?'];
  const params: SQLInputValue[] = [now];
  if (patch.title != null) {
    sets.push('title = ?');
    params.push(patch.title);
  }
  if (patch.category != null) {
    sets.push('category = ?');
    params.push(patch.category);
  }
  if (patch.amountVnd != null) {
    sets.push('amount_vnd = ?');
    params.push(patch.amountVnd);
  }
  if (patch.expenseOn != null) {
    sets.push('expense_on = ?');
    params.push(patch.expenseOn);
  }
  if (patch.notes != null) {
    sets.push('notes = ?');
    params.push(patch.notes);
  }
  params.push(expenseId);
  db.prepare(`UPDATE crm_svc_expenses SET ${sets.join(', ')} WHERE id = ?`).run(...params);
}

export function deleteExpense(db: DatabaseSync, expenseId: number): boolean {
  const result = db.prepare('DELETE FROM crm_svc_expenses WHERE id = ?').run(expenseId);
  return result.changes > 0;
}

export function getLifecycleSummary(
  db: DatabaseSync,
  lifecycleId: number,
): Record<string, unknown> {
  const lcRow = db
    .prepare('SELECT contract_id FROM crm_service_lifecycle WHERE id = ?')
    .get(lifecycleId) as Record<string, unknown> | undefined;
  if (!lcRow) {
    return {};
  }
  let contractAmountVnd = 0;
  const contractId = lcRow.contract_id;
  if (contractId != null) {
    const cRow = db
      .prepare('SELECT amount_vnd FROM crm_contracts WHERE id = ?')
      .get(Number(contractId)) as Record<string, unknown> | undefined;
    if (cRow) {
      contractAmountVnd = Number(cRow.amount_vnd ?? 0);
    }
  }
  return getFinanceSummary(db, lifecycleId, contractAmountVnd);
}

export function rowToDict(row: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(row)) out[k] = v;
  return out;
}

export { deliveryPhaseSql };
