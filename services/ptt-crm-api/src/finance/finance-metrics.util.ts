import { DatabaseSync, type SQLInputValue } from 'node:sqlite';

export const BILLING_TYPE_RECURRING = 'recurring';
export const BILLING_TYPE_ONE_OFF = 'one_off';
export const COST_PHASE_PRESALES = 'presales';
export const COST_PHASE_DELIVERY = 'delivery';

export const AR_AGING_BUCKET_KEYS = ['not_due', '1_30', '31_60', '61_90', 'over_90'] as const;

export const AR_AGING_BUCKET_LABELS: Record<string, string> = {
  not_due: 'Chưa đến hạn',
  '1_30': '1–30 ngày',
  '31_60': '31–60 ngày',
  '61_90': '61–90 ngày',
  over_90: '>90 ngày',
};

export function rowDict(row: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(row)) out[k] = v;
  return out;
}

export function tableExists(db: DatabaseSync, name: string): boolean {
  const row = db.prepare("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?").get(name);
  return row != null;
}

export function parseYmd(raw: string | null | undefined): string | null {
  const text = String(raw ?? '').trim().slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) return null;
  const [y, m, d] = text.split('-').map(Number);
  const dt = new Date(y!, m! - 1, d!);
  if (dt.getFullYear() !== y || dt.getMonth() !== m! - 1 || dt.getDate() !== d) return null;
  return text;
}

export function todayYmd(): string {
  return new Date().toISOString().slice(0, 10);
}

function agingBucket(daysOverdue: number): string {
  if (daysOverdue <= 0) return 'not_due';
  if (daysOverdue <= 30) return '1_30';
  if (daysOverdue <= 60) return '31_60';
  if (daysOverdue <= 90) return '61_90';
  return 'over_90';
}

export function resolvePaymentDueOn(payment: Record<string, unknown>): string {
  const due = parseYmd(String(payment.due_on ?? ''));
  if (due) return due;
  const recv = parseYmd(String(payment.received_on ?? ''));
  return recv ?? '';
}

function deliveryPhaseSql(): string {
  return "COALESCE(cost_phase, 'delivery') = 'delivery'";
}

function lifecycleArTotals(db: DatabaseSync, lifecycleId: number): [number, number] {
  if (!tableExists(db, 'crm_svc_payments')) return [0, 0];
  const asOf = todayYmd();
  const rows = db
    .prepare(
      "SELECT amount_vnd, due_on, received_on FROM crm_svc_payments WHERE lifecycle_id = ? AND status = 'pending'",
    )
    .all(lifecycleId) as Array<Record<string, unknown>>;
  let pending = 0;
  let overdue = 0;
  for (const row of rows) {
    const amount = Number(row.amount_vnd ?? 0);
    pending += amount;
    const dueIso = resolvePaymentDueOn(row);
    const due = parseYmd(dueIso);
    if (due && due < asOf) overdue += amount;
  }
  return [pending, overdue];
}

export function getSummary(
  db: DatabaseSync,
  lifecycleId: number,
  contractAmountVnd: number,
): Record<string, unknown> {
  if (!tableExists(db, 'crm_svc_payments')) {
    return emptySummary(contractAmountVnd);
  }
  const row = db
    .prepare(
      `
      SELECT
        COALESCE(SUM(CASE WHEN status = 'received' THEN amount_vnd ELSE 0 END), 0) AS received_revenue,
        COALESCE(SUM(CASE WHEN status = 'pending' THEN amount_vnd ELSE 0 END), 0) AS pending_revenue
      FROM crm_svc_payments WHERE lifecycle_id = ?
    `,
    )
    .get(lifecycleId) as Record<string, unknown> | undefined;
  const received = Number(row?.received_revenue ?? 0);
  const pending = Number(row?.pending_revenue ?? 0);

  let deliveryExpenses = 0;
  let presalesExpenses = 0;
  if (tableExists(db, 'crm_svc_expenses')) {
    const delRow = db
      .prepare(`SELECT COALESCE(SUM(amount_vnd), 0) AS v FROM crm_svc_expenses WHERE lifecycle_id = ? AND ${deliveryPhaseSql()}`)
      .get(lifecycleId) as Record<string, unknown> | undefined;
    deliveryExpenses = Number(delRow?.v ?? 0);
    const preRow = db
      .prepare(
        "SELECT COALESCE(SUM(amount_vnd), 0) AS v FROM crm_svc_expenses WHERE lifecycle_id = ? AND cost_phase = ?",
      )
      .get(lifecycleId, COST_PHASE_PRESALES) as Record<string, unknown> | undefined;
    presalesExpenses = Number(preRow?.v ?? 0);
  }

  const totalExpenses = deliveryExpenses + presalesExpenses;
  const profit = received - deliveryExpenses;
  const marginPct = received > 0 ? Math.round((profit / received) * 10000) / 100 : 0;
  const outstanding = contractAmountVnd - received;
  const [arPending, arOverdue] = lifecycleArTotals(db, lifecycleId);

  return {
    expected_revenue: contractAmountVnd,
    received_revenue: received,
    pending_revenue: pending,
    ar_pending_vnd: arPending,
    ar_overdue_vnd: arOverdue,
    delivery_expenses: deliveryExpenses,
    presales_expenses: presalesExpenses,
    total_expenses: totalExpenses,
    profit,
    margin_pct: marginPct,
    outstanding,
  };
}

function emptySummary(contractAmountVnd: number): Record<string, unknown> {
  return {
    expected_revenue: contractAmountVnd,
    received_revenue: 0,
    pending_revenue: 0,
    ar_pending_vnd: 0,
    ar_overdue_vnd: 0,
    delivery_expenses: 0,
    presales_expenses: 0,
    total_expenses: 0,
    profit: 0,
    margin_pct: 0,
    outstanding: contractAmountVnd,
  };
}

export function getArAging(
  db: DatabaseSync,
  opts: { asOf?: string | null; amId?: number | null } = {},
): Record<string, unknown> {
  const asOfIso = parseYmd(opts.asOf ?? '') ?? todayYmd();
  const asOfDate = new Date(asOfIso + 'T00:00:00');
  if (!tableExists(db, 'crm_svc_payments') || !tableExists(db, 'crm_service_lifecycle')) {
    return emptyArAging(asOfIso, opts.amId ?? null);
  }

  const where = ["p.status = 'pending'"];
  const params: SQLInputValue[] = [];
  if (opts.amId != null) {
    where.push('lc.assigned_am = ?');
    params.push(opts.amId);
  }

  const rows = db
    .prepare(
      `
      SELECT p.id, p.lifecycle_id, p.amount_vnd, p.received_on, p.due_on, p.status,
             p.notes, lc.assigned_am, lc.service_slug, lc.customer_id,
             cu.name AS customer_name,
             COALESCE(ct.billing_type, '${BILLING_TYPE_ONE_OFF}') AS billing_type
      FROM crm_svc_payments p
      INNER JOIN crm_service_lifecycle lc ON lc.id = p.lifecycle_id
      LEFT JOIN crm_customers cu ON cu.id = lc.customer_id
      LEFT JOIN crm_contracts ct ON ct.id = lc.contract_id
      WHERE ${where.join(' AND ')}
      ORDER BY p.due_on ASC, p.id ASC
    `,
    )
    .all(...params) as Array<Record<string, unknown>>;

  const buckets: Record<string, number> = {};
  for (const key of AR_AGING_BUCKET_KEYS) buckets[key] = 0;
  const items: Record<string, unknown>[] = [];
  let totalPending = 0;
  let totalOverdue = 0;

  for (const d of rows) {
    const amount = Number(d.amount_vnd ?? 0);
    const dueIso = resolvePaymentDueOn(d);
    const due = parseYmd(dueIso);
    let daysOverdue = 0;
    let bucket = 'not_due';
    if (due) {
      daysOverdue = Math.floor((asOfDate.getTime() - new Date(due + 'T00:00:00').getTime()) / 86400000);
      bucket = agingBucket(daysOverdue);
    }
    buckets[bucket] = (buckets[bucket] ?? 0) + amount;
    totalPending += amount;
    if (daysOverdue > 0) totalOverdue += amount;
    items.push({
      payment_id: Number(d.id),
      lifecycle_id: Number(d.lifecycle_id),
      amount_vnd: amount,
      due_on: dueIso,
      days_overdue: Math.max(0, daysOverdue),
      bucket,
      customer_name: d.customer_name ?? '—',
      service_slug: d.service_slug ?? '',
      billing_type: String(d.billing_type ?? BILLING_TYPE_ONE_OFF),
      assigned_am: d.assigned_am,
      notes: d.notes ?? '',
    });
  }

  return {
    as_of: asOfIso,
    am_id: opts.amId ?? null,
    total_pending_vnd: totalPending,
    total_overdue_vnd: totalOverdue,
    buckets,
    bucket_labels: AR_AGING_BUCKET_LABELS,
    items,
  };
}

function emptyArAging(asOf: string, amId: number | null): Record<string, unknown> {
  const buckets: Record<string, number> = {};
  for (const key of AR_AGING_BUCKET_KEYS) buckets[key] = 0;
  return {
    as_of: asOf,
    am_id: amId,
    total_pending_vnd: 0,
    total_overdue_vnd: 0,
    buckets,
    bucket_labels: AR_AGING_BUCKET_LABELS,
    items: [],
  };
}

export function getRecurringRevenueSummary(
  db: DatabaseSync,
  year: number,
  month: number,
  amId?: number | null,
): Record<string, unknown> {
  const monthStr = `${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}`;
  if (!tableExists(db, 'crm_svc_payments') || !tableExists(db, 'crm_service_lifecycle')) {
    return {
      year,
      month,
      am_id: amId ?? null,
      received_recurring_vnd: 0,
      pending_recurring_vnd: 0,
      active_recurring_contracts: 0,
    };
  }

  const amClause = amId != null ? ' AND lc.assigned_am = ?' : '';
  const amParams = amId != null ? [amId] : [];

  const recvRow = db
    .prepare(
      `
      SELECT COALESCE(SUM(p.amount_vnd), 0) AS v
      FROM crm_svc_payments p
      INNER JOIN crm_service_lifecycle lc ON lc.id = p.lifecycle_id
      INNER JOIN crm_contracts ct ON ct.id = lc.contract_id
      WHERE ct.billing_type = ?
        AND p.status = 'received'
        AND p.received_on LIKE ?
        ${amClause}
    `,
    )
    .get(BILLING_TYPE_RECURRING, `${monthStr}%`, ...amParams) as Record<string, unknown> | undefined;

  const pendingRow = db
    .prepare(
      `
      SELECT COALESCE(SUM(p.amount_vnd), 0) AS v
      FROM crm_svc_payments p
      INNER JOIN crm_service_lifecycle lc ON lc.id = p.lifecycle_id
      INNER JOIN crm_contracts ct ON ct.id = lc.contract_id
      WHERE ct.billing_type = ? AND p.status = 'pending' ${amClause}
    `,
    )
    .get(BILLING_TYPE_RECURRING, ...amParams) as Record<string, unknown> | undefined;

  const activeRow = db
    .prepare(
      `
      SELECT COUNT(DISTINCT ct.id) AS v
      FROM crm_contracts ct
      INNER JOIN crm_service_lifecycle lc ON lc.contract_id = ct.id
      WHERE ct.billing_type = ?
        AND ct.status IN ('active', 'signed', 'expiring')
        AND lc.status = 'active'
        ${amClause}
    `,
    )
    .get(BILLING_TYPE_RECURRING, ...amParams) as Record<string, unknown> | undefined;

  return {
    year,
    month,
    am_id: amId ?? null,
    received_recurring_vnd: Number(recvRow?.v ?? 0),
    pending_recurring_vnd: Number(pendingRow?.v ?? 0),
    active_recurring_contracts: Number(activeRow?.v ?? 0),
  };
}

function emptyPackageBucket(): Record<string, unknown> {
  return {
    lifecycle_count: 0,
    expected_revenue_vnd: 0,
    received_month_vnd: 0,
    delivery_expenses_month_vnd: 0,
    gross_margin_month_pct: 0,
    received_lifetime_vnd: 0,
    delivery_expenses_lifetime_vnd: 0,
    gross_margin_lifetime_pct: 0,
    profit_lifetime_vnd: 0,
    ar_overdue_vnd: 0,
    outstanding_vnd: 0,
  };
}

function pctMargin(revenue: number, cost: number): number {
  if (revenue <= 0) return 0;
  return Math.round(((revenue - cost) / revenue) * 10000) / 100;
}

export function getServicePackageRollup(
  db: DatabaseSync,
  year: number,
  month: number,
  lifecycleStatus = 'active',
): Record<string, unknown> {
  const monthPrefix = `${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}`;
  if (!tableExists(db, 'crm_service_lifecycle')) {
    return { year, month, packages: [] as Record<string, unknown>[] };
  }

  const lcRows = db
    .prepare(
      'SELECT lc.id, lc.service_slug, lc.contract_id FROM crm_service_lifecycle lc WHERE lc.status = ? ORDER BY lc.service_slug, lc.id',
    )
    .all(lifecycleStatus) as Array<Record<string, unknown>>;

  const packages: Record<string, Record<string, unknown>> = {};
  for (const lc of lcRows) {
    const slug = String(lc.service_slug ?? '').trim() || '_unknown';
    if (!packages[slug]) {
      packages[slug] = { ...emptyPackageBucket(), service_slug: slug, service_label: slug };
    }
    const bucket = packages[slug]!;
    const lcId = Number(lc.id);
    let contractAmount = 0;
    if (lc.contract_id && tableExists(db, 'crm_contracts')) {
      const cRow = db
        .prepare('SELECT amount_vnd FROM crm_contracts WHERE id = ?')
        .get(Number(lc.contract_id)) as Record<string, unknown> | undefined;
      contractAmount = Number(cRow?.amount_vnd ?? 0);
    }
    const summary = getSummary(db, lcId, contractAmount);
    bucket.lifecycle_count = Number(bucket.lifecycle_count) + 1;
    bucket.expected_revenue_vnd = Number(bucket.expected_revenue_vnd) + contractAmount;
    bucket.received_lifetime_vnd = Number(bucket.received_lifetime_vnd) + Number(summary.received_revenue);
    bucket.delivery_expenses_lifetime_vnd =
      Number(bucket.delivery_expenses_lifetime_vnd) + Number(summary.delivery_expenses);
    bucket.profit_lifetime_vnd = Number(bucket.profit_lifetime_vnd) + Number(summary.profit);
    bucket.ar_overdue_vnd = Number(bucket.ar_overdue_vnd) + Number(summary.ar_overdue_vnd);
    bucket.outstanding_vnd = Number(bucket.outstanding_vnd) + Number(summary.outstanding);

    if (tableExists(db, 'crm_svc_payments')) {
      const recvMonth = db
        .prepare(
          "SELECT COALESCE(SUM(amount_vnd), 0) AS v FROM crm_svc_payments WHERE lifecycle_id = ? AND status = 'received' AND received_on LIKE ?",
        )
        .get(lcId, `${monthPrefix}%`) as Record<string, unknown> | undefined;
      bucket.received_month_vnd = Number(bucket.received_month_vnd) + Number(recvMonth?.v ?? 0);
    }
    if (tableExists(db, 'crm_svc_expenses')) {
      const expMonth = db
        .prepare(
          `SELECT COALESCE(SUM(amount_vnd), 0) AS v FROM crm_svc_expenses WHERE lifecycle_id = ? AND ${deliveryPhaseSql()} AND expense_on LIKE ?`,
        )
        .get(lcId, `${monthPrefix}%`) as Record<string, unknown> | undefined;
      bucket.delivery_expenses_month_vnd =
        Number(bucket.delivery_expenses_month_vnd) + Number(expMonth?.v ?? 0);
    }
  }

  const pkgList = Object.values(packages).map((p) => {
    p.gross_margin_month_pct = pctMargin(
      Number(p.received_month_vnd),
      Number(p.delivery_expenses_month_vnd),
    );
    p.gross_margin_lifetime_pct = pctMargin(
      Number(p.received_lifetime_vnd),
      Number(p.delivery_expenses_lifetime_vnd),
    );
    return p;
  });

  return { year, month, packages: pkgList };
}

export function getLeadKpiSummary(
  db: DatabaseSync,
  year: number,
  month: number,
  staffId?: number | null,
): Record<string, unknown> {
  const monthPrefix = `${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}`;
  if (!tableExists(db, 'crm_leads')) {
    return emptyLeadKpi(year, month, staffId ?? null);
  }

  const staffClause = staffId != null ? ' AND assigned_staff_id = ?' : '';
  const staffParams = staffId != null ? [staffId] : [];

  const qualifiedRow = db
    .prepare(
      `SELECT COUNT(*) AS v FROM crm_leads WHERE status = 'qualified' AND substr(replace(trim(created_at), 'T', ' '), 1, 7) = ?${staffClause}`,
    )
    .get(`${monthPrefix}`, ...staffParams) as Record<string, unknown> | undefined;

  const wonRow = db
    .prepare(
      `SELECT COUNT(*) AS v FROM crm_leads WHERE status = 'won' AND substr(replace(trim(updated_at), 'T', ' '), 1, 7) = ?${staffClause}`,
    )
    .get(`${monthPrefix}`, ...staffParams) as Record<string, unknown> | undefined;

  const qualified = Number(qualifiedRow?.v ?? 0);
  const won = Number(wonRow?.v ?? 0);
  const closeRate = qualified > 0 ? Math.round((won / qualified) * 10000) / 100 : 0;

  return {
    year,
    month,
    staff_id: staffId ?? null,
    qualified_in_month: qualified,
    won_from_month_cohort: won,
    cohort_close_rate_pct: closeRate,
    cohort_close_rate_decided_pct: closeRate,
    qualified_leads: qualified,
    close_rate_pct: closeRate,
  };
}

function emptyLeadKpi(year: number, month: number, staffId: number | null): Record<string, unknown> {
  return {
    year,
    month,
    staff_id: staffId,
    qualified_in_month: 0,
    won_from_month_cohort: 0,
    cohort_close_rate_pct: 0,
    cohort_close_rate_decided_pct: 0,
    qualified_leads: 0,
    close_rate_pct: 0,
  };
}

export function ensurePeriodInputsSchema(db: DatabaseSync): void {
  db.exec(`
    CREATE TABLE IF NOT EXISTS crm_finance_period_inputs (
      year INTEGER NOT NULL,
      month INTEGER NOT NULL,
      marketing_spend_vnd INTEGER NOT NULL DEFAULT 0,
      updated_at TEXT NOT NULL DEFAULT '',
      PRIMARY KEY (year, month)
    )
  `);
}

export function getMarketingSpendVnd(
  db: DatabaseSync,
  year: number,
  month: number,
): [number, string] {
  ensurePeriodInputsSchema(db);
  const row = db
    .prepare('SELECT marketing_spend_vnd FROM crm_finance_period_inputs WHERE year = ? AND month = ?')
    .get(year, month) as Record<string, unknown> | undefined;
  if (row) return [Number(row.marketing_spend_vnd ?? 0), 'db'];
  const envRaw = String(process.env.PTT_MONTHLY_MARKETING_SPEND_VND ?? '').trim();
  const envVal = envRaw ? Math.max(0, Number(envRaw) || 0) : 0;
  return [envVal, envRaw ? 'env' : 'default'];
}

export function setMarketingSpendVnd(
  db: DatabaseSync,
  year: number,
  month: number,
  amountVnd: number,
): void {
  ensurePeriodInputsSchema(db);
  const ts = new Date().toISOString().replace('T', ' ').slice(0, 19);
  db.prepare(
    `
    INSERT INTO crm_finance_period_inputs (year, month, marketing_spend_vnd, updated_at)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(year, month) DO UPDATE SET
      marketing_spend_vnd = excluded.marketing_spend_vnd,
      updated_at = excluded.updated_at
  `,
  ).run(year, month, amountVnd, ts);
}

export function getCacMetrics(db: DatabaseSync, year: number, month: number): Record<string, unknown> {
  const monthPrefix = `${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}`;
  let presalesCost = 0;
  if (tableExists(db, 'crm_svc_expenses')) {
    const row = db
      .prepare(
        "SELECT COALESCE(SUM(amount_vnd), 0) AS v FROM crm_svc_expenses WHERE cost_phase = ? AND expense_on LIKE ?",
      )
      .get(COST_PHASE_PRESALES, `${monthPrefix}%`) as Record<string, unknown> | undefined;
    presalesCost = Number(row?.v ?? 0);
  }
  const [marketingCost, marketingSource] = getMarketingSpendVnd(db, year, month);

  let newCustomers = 0;
  if (tableExists(db, 'crm_customers')) {
    const row = db
      .prepare(
        "SELECT COUNT(*) AS v FROM crm_customers WHERE substr(replace(trim(created_at), 'T', ' '), 1, 7) = ?",
      )
      .get(`${monthPrefix}`) as Record<string, unknown> | undefined;
    newCustomers = Number(row?.v ?? 0);
  }

  const totalCost = presalesCost + marketingCost;
  const cac = newCustomers > 0 ? Math.round(totalCost / newCustomers) : 0;

  return {
    year,
    month,
    cac_vnd: cac,
    new_customers: newCustomers,
    presales_cost_vnd: presalesCost,
    marketing_cost_vnd: marketingCost,
    marketing_spend_source: marketingSource,
  };
}

export function getMrrArrMetrics(db: DatabaseSync, year: number, month: number): Record<string, unknown> {
  const rec = getRecurringRevenueSummary(db, year, month);
  const mrr = Number(rec.received_recurring_vnd ?? 0);
  return {
    year,
    month,
    mrr_bookings_vnd: mrr,
    mrr_cash_vnd: mrr,
    arr_bookings_vnd: mrr * 12,
  };
}

export function getConcentrationMetrics(db: DatabaseSync, year: number, month: number): Record<string, unknown> {
  const monthPrefix = `${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}`;
  if (!tableExists(db, 'crm_svc_payments') || !tableExists(db, 'crm_service_lifecycle')) {
    return {
      year,
      month,
      total_received_vnd: 0,
      top1_share_pct: 0,
      top2_concentration_pct: 0,
      top_customers: [] as Record<string, unknown>[],
    };
  }

  const rows = db
    .prepare(
      `
      SELECT cu.id AS customer_id, cu.name AS customer_name, COALESCE(SUM(p.amount_vnd), 0) AS received_vnd
      FROM crm_svc_payments p
      INNER JOIN crm_service_lifecycle lc ON lc.id = p.lifecycle_id
      LEFT JOIN crm_customers cu ON cu.id = lc.customer_id
      WHERE p.status = 'received' AND p.received_on LIKE ?
      GROUP BY cu.id, cu.name
      ORDER BY received_vnd DESC
    `,
    )
    .all(`${monthPrefix}%`) as Array<Record<string, unknown>>;

  const total = rows.reduce((s, r) => s + Number(r.received_vnd ?? 0), 0);
  const topCustomers = rows.slice(0, 5).map((r) => ({
    customer_id: r.customer_id,
    customer_name: r.customer_name ?? '—',
    received_vnd: Number(r.received_vnd ?? 0),
    share_pct: total > 0 ? Math.round((Number(r.received_vnd ?? 0) / total) * 10000) / 100 : 0,
  }));

  const top1 = topCustomers[0]?.share_pct ?? 0;
  const top2 =
    topCustomers.length >= 2
      ? Math.round(((Number(topCustomers[0]?.received_vnd ?? 0) + Number(topCustomers[1]?.received_vnd ?? 0)) / (total || 1)) * 10000) / 100
      : top1;

  return {
    year,
    month,
    total_received_vnd: total,
    top1_share_pct: top1,
    top2_concentration_pct: top2,
    top_customers: topCustomers,
  };
}

export function getPortfolioMetrics(db: DatabaseSync, year: number, month: number): Record<string, unknown> {
  const concentration = getConcentrationMetrics(db, year, month);
  const capacity = {
    year,
    month,
    am_utilization_pct: 0,
    sp_utilization_pct: 0,
    combined_utilization_pct: 0,
  };
  return { year, month, concentration, capacity };
}

export function getRetentionMetrics(db: DatabaseSync, year: number, month: number): Record<string, unknown> {
  const prev = prevMonth(year, month);
  let active = 0;
  let activePrev = 0;
  if (tableExists(db, 'crm_service_lifecycle')) {
    const row = db
      .prepare("SELECT COUNT(DISTINCT customer_id) AS v FROM crm_service_lifecycle WHERE status = 'active'")
      .get() as Record<string, unknown> | undefined;
    active = Number(row?.v ?? 0);
    activePrev = active;
  }
  const retentionPct = activePrev > 0 ? Math.round((active / activePrev) * 10000) / 100 : 100;
  const churnPct = Math.max(0, 100 - retentionPct);
  return {
    year,
    month,
    active_customers: active,
    active_customers_prev: activePrev,
    customer_retention_pct: retentionPct,
    customer_churn_pct: churnPct,
    renewal_cohort: {
      contracts_ending: 0,
      renewed: 0,
      churned: 0,
      contracts_decided: 0,
      renewal_rate_pct: 0,
    },
  };
}

export function getExecMetrics(db: DatabaseSync, year: number, month: number): Record<string, unknown> {
  return {
    year,
    month,
    cac: getCacMetrics(db, year, month),
    mrr_arr: getMrrArrMetrics(db, year, month),
    delivery_ontime: {
      year,
      month,
      on_time_rate_pct: 0,
      tasks_on_time: 0,
      tasks_decided: 0,
    },
  };
}

export function getFinancialLifecycleRows(db: DatabaseSync): Record<string, unknown>[] {
  if (!tableExists(db, 'crm_service_lifecycle')) return [];
  const lcs = db
    .prepare(
      `
      SELECT lc.id, lc.service_slug, lc.stage, lc.contract_id, lc.customer_id,
             cu.name AS customer_name
      FROM crm_service_lifecycle lc
      LEFT JOIN crm_customers cu ON cu.id = lc.customer_id
      WHERE lc.status = 'active'
      ORDER BY lc.id
    `,
    )
    .all() as Array<Record<string, unknown>>;

  const rows: Record<string, unknown>[] = [];
  for (const lc of lcs) {
    let contractAmount = 0;
    if (lc.contract_id && tableExists(db, 'crm_contracts')) {
      const cRow = db
        .prepare('SELECT amount_vnd FROM crm_contracts WHERE id = ?')
        .get(Number(lc.contract_id)) as Record<string, unknown> | undefined;
      contractAmount = Number(cRow?.amount_vnd ?? 0);
    }
    const summary = getSummary(db, Number(lc.id), contractAmount);
    rows.push({
      lifecycle_id: lc.id,
      service_slug: lc.service_slug,
      service_label: lc.service_slug,
      stage: lc.stage,
      customer_name: lc.customer_name ?? '—',
      ...summary,
    });
  }
  rows.sort((a, b) => Number(a.margin_pct) - Number(b.margin_pct));
  return rows;
}

function prevMonth(year: number, month: number): [number, number] {
  if (month === 1) return [year - 1, 12];
  return [year, month - 1];
}

export function getFinanceKpiInboxSummary(db: DatabaseSync): Record<string, unknown> {
  if (!tableExists(db, 'crm_reminders')) {
    return { pending_count: 0, critical_count: 0, warning_count: 0, items: [] };
  }
  const rows = db
    .prepare(
      `
      SELECT id, title, body, remind_at, status, meta_json
      FROM crm_reminders
      WHERE scope = 'finance_kpi' AND reminder_kind = 'kpi_alert' AND status = 'pending'
      ORDER BY remind_at ASC, id ASC
      LIMIT 100
    `,
    )
    .all() as Array<Record<string, unknown>>;

  const items: Record<string, unknown>[] = [];
  let critical = 0;
  let warning = 0;
  for (const d of rows) {
    let meta: Record<string, unknown> = {};
    try {
      meta = JSON.parse(String(d.meta_json ?? '{}')) as Record<string, unknown>;
    } catch {
      meta = {};
    }
    const level = String(meta.level ?? '');
    if (level === 'critical') critical += 1;
    else warning += 1;
    items.push({
      id: Number(d.id),
      title: d.title ?? '',
      body: d.body ?? '',
      remind_at: d.remind_at ?? '',
      level,
      dashboard_url: meta.dashboard_url ?? '',
      year: meta.year,
      month: meta.month,
    });
  }
  return { pending_count: items.length, critical_count: critical, warning_count: warning, items };
}
