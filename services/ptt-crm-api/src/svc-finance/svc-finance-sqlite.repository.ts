import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { DatabaseSync } from 'node:sqlite';
import { AppConfigService } from '../config/app-config.service';

export interface SvcPaymentRow {
  id: number;
  lifecycle_id: number;
  amount_vnd: number;
  received_on: string;
  due_on: string | null;
  status: string;
  notes: string;
  created_at: string;
}

@Injectable()
export class SvcFinanceSqliteRepository implements OnModuleDestroy {
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

  lifecycleExists(lifecycleId: number): boolean {
    const row = this.database
      .prepare('SELECT id FROM crm_service_lifecycle WHERE id = ?')
      .get(lifecycleId) as { id: number } | undefined;
    return row != null;
  }

  contractAmountVnd(lifecycleId: number): number {
    const row = this.database
      .prepare(
        `
        SELECT c.amount_vnd
        FROM crm_service_lifecycle lc
        LEFT JOIN crm_contracts c ON c.id = lc.contract_id
        WHERE lc.id = ?
        `,
      )
      .get(lifecycleId) as { amount_vnd: number | null } | undefined;
    return Number(row?.amount_vnd ?? 0);
  }

  getSummary(lifecycleId: number, contractAmountVnd: number): Record<string, unknown> {
    const payRow = this.database
      .prepare(
        `
        SELECT
          COALESCE(SUM(CASE WHEN status = 'received' THEN amount_vnd ELSE 0 END), 0) AS received_revenue,
          COALESCE(SUM(CASE WHEN status = 'pending' THEN amount_vnd ELSE 0 END), 0) AS pending_revenue
        FROM crm_svc_payments WHERE lifecycle_id = ?
        `,
      )
      .get(lifecycleId) as { received_revenue: number; pending_revenue: number };

    const deliveryRow = this.database
      .prepare(
        `
        SELECT COALESCE(SUM(amount_vnd), 0) AS total
        FROM crm_svc_expenses
        WHERE lifecycle_id = ?
          AND COALESCE(NULLIF(cost_phase, ''), 'delivery') = 'delivery'
        `,
      )
      .get(lifecycleId) as { total: number };

    const presalesRow = this.database
      .prepare(
        `
        SELECT COALESCE(SUM(amount_vnd), 0) AS total
        FROM crm_svc_expenses
        WHERE lifecycle_id = ? AND cost_phase = 'presales'
        `,
      )
      .get(lifecycleId) as { total: number };

    const received = Number(payRow.received_revenue ?? 0);
    const pending = Number(payRow.pending_revenue ?? 0);
    const deliveryExpenses = Number(deliveryRow.total ?? 0);
    const presalesExpenses = Number(presalesRow.total ?? 0);
    const totalExpenses = deliveryExpenses + presalesExpenses;
    const profit = received - deliveryExpenses;
    const marginPct = received > 0 ? (profit / received) * 100 : 0;
    const outstanding = contractAmountVnd - received;

    return {
      expected_revenue: contractAmountVnd,
      received_revenue: received,
      pending_revenue: pending,
      delivery_expenses: deliveryExpenses,
      presales_expenses: presalesExpenses,
      total_expenses: totalExpenses,
      profit_vnd: profit,
      margin_pct: marginPct,
      outstanding_vnd: outstanding,
      lifecycle_id: lifecycleId,
    };
  }

  createPayment(body: Record<string, unknown>): SvcPaymentRow {
    const lifecycleId = Number(body.lifecycle_id);
    const amountVnd = Number(body.amount_vnd);
    const receivedOn = String(body.received_on ?? '').slice(0, 10);
    const dueOn = body.due_on ? String(body.due_on).slice(0, 10) : null;
    const status = String(body.status ?? 'pending').trim();
    const notes = String(body.notes ?? '').trim();
    const now = new Date().toISOString().slice(0, 19).replace('T', ' ');
    const result = this.database
      .prepare(
        `
        INSERT INTO crm_svc_payments (
          lifecycle_id, amount_vnd, received_on, due_on, status, notes, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        `,
      )
      .run(lifecycleId, amountVnd, receivedOn, dueOn, status, notes, now);
    return this.getPaymentById(Number(result.lastInsertRowid))!;
  }

  getPaymentById(id: number): SvcPaymentRow | null {
    const row = this.database
      .prepare('SELECT * FROM crm_svc_payments WHERE id = ?')
      .get(id) as SvcPaymentRow | undefined;
    return row ?? null;
  }

  patchPayment(id: number, body: Record<string, unknown>): SvcPaymentRow | null {
    const existing = this.getPaymentById(id);
    if (!existing) return null;
    const amountVnd = body.amount_vnd != null ? Number(body.amount_vnd) : existing.amount_vnd;
    const receivedOn =
      body.received_on != null ? String(body.received_on).slice(0, 10) : existing.received_on;
    const dueOn = body.due_on != null ? String(body.due_on).slice(0, 10) : existing.due_on;
    const status = body.status != null ? String(body.status).trim() : existing.status;
    const notes = body.notes != null ? String(body.notes).trim() : existing.notes;
    this.database
      .prepare(
        `
        UPDATE crm_svc_payments
        SET amount_vnd = ?, received_on = ?, due_on = ?, status = ?, notes = ?
        WHERE id = ?
        `,
      )
      .run(amountVnd, receivedOn, dueOn, status, notes, id);
    return this.getPaymentById(id);
  }

  deletePayment(id: number): boolean {
    const result = this.database.prepare('DELETE FROM crm_svc_payments WHERE id = ?').run(id);
    return result.changes > 0;
  }
}
