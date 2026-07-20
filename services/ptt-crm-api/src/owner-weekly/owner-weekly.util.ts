import { DatabaseSync } from 'node:sqlite';
import { ensureKpiConfigSchema } from '../finance/finance-kpi.util';
import {
  COST_PHASE_DELIVERY,
  COST_PHASE_PRESALES,
  getArAging,
  parseYmd,
  tableExists,
  todayYmd,
} from '../finance/finance-metrics.util';

export const RAG_GREEN = 'green';
export const RAG_YELLOW = 'yellow';
export const RAG_RED = 'red';

export const RAG_LABELS: Record<string, string> = {
  [RAG_GREEN]: 'Đạt / vượt target',
  [RAG_YELLOW]: 'Lệch nhẹ — theo dõi sát',
  [RAG_RED]: 'Cần xử lý trong 7 ngày',
};

export const BLOCK_KEYS = ['cash', 'sales', 'efficiency', 'risk'] as const;
export const BLOCK_LABELS: Record<string, string> = {
  cash: 'Tiền',
  sales: 'Kinh doanh',
  efficiency: 'Hiệu quả',
  risk: 'Rủi ro',
};

export const OWNER_WEEKLY_TARGET_DEFAULTS: Record<string, number> = {
  cash_safe_min_vnd: 50_000_000,
  cash_forecast_min_vnd: 0,
  ar_overdue_max_vnd: 30_000_000,
  lead_new_target: 5,
  lead_qualified_target: 3,
  proposals_target: 2,
  deals_closed_target: 1,
  revenue_target_vnd: 20_000_000,
  pipeline_next_min_vnd: 50_000_000,
  gross_margin_target_pct: 30,
  net_margin_target_pct: 15,
  cac_max_vnd: 15_000_000,
  roas_min: 3,
  cycle_time_max_days: 45,
  ontime_target_pct: 85,
  close_rate_target_pct: 30,
  bad_debt_min_vnd: 10_000_000,
  bad_debt_min_days: 30,
  late_projects_max: 0,
  stuck_work_max: 3,
  capacity_max_util_pct: 85,
  top_deal_share_max_pct: 40,
  top1_share_max_pct: 40,
  churn_max_pct: 10,
  win_rate_drop_warn_pct: 15,
  win_rate_drop_critical_pct: 20,
};

export const OWNER_WEEKLY_ENV_KEYS: Record<string, string> = Object.fromEntries(
  Object.keys(OWNER_WEEKLY_TARGET_DEFAULTS).map((k) => [k, `PTT_OWNER_WEEKLY_${k.toUpperCase()}`]),
);

export const OWNER_WEEKLY_TARGET_LABELS: Record<string, string> = {
  cash_safe_min_vnd: 'Tiền an toàn tối thiểu (VNĐ)',
  cash_forecast_min_vnd: 'Cash forecast 30 ngày tối thiểu (VNĐ)',
  ar_overdue_max_vnd: 'AR quá hạn tối đa (VNĐ)',
  lead_new_target: 'Lead mới / tuần',
  lead_qualified_target: 'Lead đủ chuẩn / tuần',
  proposals_target: 'Báo giá gửi / tuần',
  deals_closed_target: 'Deal chốt / tuần',
  revenue_target_vnd: 'Doanh thu tuần (VNĐ)',
  pipeline_next_min_vnd: 'Pipeline tối thiểu (VNĐ)',
  gross_margin_target_pct: 'Gross margin target (%)',
  net_margin_target_pct: 'Net margin target (%)',
  cac_max_vnd: 'CAC tối đa (VNĐ)',
  roas_min: 'ROAS tối thiểu',
  cycle_time_max_days: 'Cycle time tối đa (ngày)',
  ontime_target_pct: 'On-time delivery target (%)',
  close_rate_target_pct: 'Win rate target (%)',
  bad_debt_min_vnd: 'Nợ xấu tối thiểu / KH (VNĐ)',
  bad_debt_min_days: 'Nợ xấu — ngày quá hạn tối thiểu',
  late_projects_max: 'Dự án trễ tối đa',
  stuck_work_max: 'Đầu việc kẹt tối đa',
  capacity_max_util_pct: 'Utilization tối đa (%)',
  top_deal_share_max_pct: 'Deal phụ thuộc tối đa (%)',
  top1_share_max_pct: 'Top-1 DT tối đa (%)',
  churn_max_pct: 'Churn tối đa (%)',
  win_rate_drop_warn_pct: 'Win rate giảm — cảnh báo (%)',
  win_rate_drop_critical_pct: 'Win rate giảm — nghiêm trọng (%)',
};

export const OWNER_WEEKLY_TARGET_GROUPS: Array<[string, string, string[]]> = [
  ['cash', 'Tiền', ['cash_safe_min_vnd', 'cash_forecast_min_vnd', 'ar_overdue_max_vnd', 'revenue_target_vnd']],
  [
    'sales',
    'Kinh doanh',
    ['lead_new_target', 'lead_qualified_target', 'proposals_target', 'deals_closed_target', 'pipeline_next_min_vnd', 'close_rate_target_pct'],
  ],
  [
    'efficiency',
    'Hiệu quả',
    ['gross_margin_target_pct', 'net_margin_target_pct', 'cac_max_vnd', 'roas_min', 'cycle_time_max_days', 'ontime_target_pct'],
  ],
  [
    'risk',
    'Rủi ro',
    [
      'bad_debt_min_vnd',
      'bad_debt_min_days',
      'late_projects_max',
      'stuck_work_max',
      'capacity_max_util_pct',
      'top_deal_share_max_pct',
      'top1_share_max_pct',
      'churn_max_pct',
      'win_rate_drop_warn_pct',
      'win_rate_drop_critical_pct',
    ],
  ],
];

const CASH_SOURCE_MANUAL = 'manual';
const CASH_SOURCE_BANK = 'bank';
const CASH_SOURCES = new Set([CASH_SOURCE_MANUAL, CASH_SOURCE_BANK]);
export const POSITION_SOURCE_LEDGER = 'ledger';
export const POSITION_SOURCE_PROXY = 'proxy';

function envNumber(name: string, defaultVal: number): number {
  const raw = String(process.env[name] ?? '').trim();
  if (!raw) return defaultVal;
  const n = Number(raw);
  return Number.isFinite(n) ? n : defaultVal;
}

function addDays(iso: string, days: number): string {
  const d = new Date(iso + 'T00:00:00');
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

function formatDdMm(iso: string): string {
  const [y, m, d] = iso.split('-');
  return `${d}/${m}`;
}

export function dateFromIsoWeek(year: number, week: number, day: number): string {
  const simple = new Date(Date.UTC(year, 0, 1 + (week - 1) * 7));
  const dow = simple.getUTCDay();
  const isoWeekStart = new Date(simple);
  if (dow <= 4) isoWeekStart.setUTCDate(simple.getUTCDate() - simple.getUTCDay() + 1);
  else isoWeekStart.setUTCDate(simple.getUTCDate() + 8 - simple.getUTCDay());
  isoWeekStart.setUTCDate(isoWeekStart.getUTCDate() + (day - 1));
  return isoWeekStart.toISOString().slice(0, 10);
}

export function resolveWeekBounds(opts: {
  weekEnd?: string | null;
  year?: number | null;
  isoWeek?: number | null;
}): { start: string; end: string; isoYear: number; isoWeek: number } {
  if (opts.year != null && opts.isoWeek != null) {
    const start = dateFromIsoWeek(opts.year, opts.isoWeek, 1);
    const end = dateFromIsoWeek(opts.year, opts.isoWeek, 7);
    return { start, end, isoYear: opts.year, isoWeek: opts.isoWeek };
  }

  let end: string;
  if (opts.weekEnd && parseYmd(opts.weekEnd)) {
    end = parseYmd(opts.weekEnd)!;
  } else {
    const today = todayYmd();
    const day = new Date(today + 'T00:00:00').getDay();
    const daysSinceMonday = day === 0 ? 6 : day - 1;
    const thisMonday = addDays(today, -daysSinceMonday);
    end = addDays(thisMonday, -1);
  }
  const start = addDays(end, -6);
  const startDate = new Date(start + 'T00:00:00');
  const tmp = new Date(Date.UTC(startDate.getFullYear(), startDate.getMonth(), startDate.getDate()));
  tmp.setUTCDate(tmp.getUTCDate() + 4 - (tmp.getUTCDay() || 7));
  const yearStart = new Date(Date.UTC(tmp.getUTCFullYear(), 0, 1));
  const isoWeek = Math.ceil(((tmp.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
  return { start, end, isoYear: tmp.getUTCFullYear(), isoWeek };
}

export function ensureCashLedgerSchema(db: DatabaseSync): void {
  db.exec(`
    CREATE TABLE IF NOT EXISTS crm_owner_cash_snapshots (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      snapshot_on TEXT NOT NULL,
      balance_vnd INTEGER NOT NULL DEFAULT 0,
      source TEXT NOT NULL DEFAULT 'manual',
      notes TEXT NOT NULL DEFAULT '',
      updated_at TEXT NOT NULL DEFAULT ''
    )
  `);
  db.exec(`
    CREATE UNIQUE INDEX IF NOT EXISTS idx_owner_cash_snapshots_on
    ON crm_owner_cash_snapshots(snapshot_on)
  `);
}

function sumReceivedBetween(db: DatabaseSync, start: string, end: string): number {
  if (start > end || !tableExists(db, 'crm_svc_payments')) return 0;
  const row = db
    .prepare(
      `
      SELECT COALESCE(SUM(amount_vnd), 0) AS v FROM crm_svc_payments
      WHERE status = 'received'
        AND substr(received_on, 1, 10) >= ?
        AND substr(received_on, 1, 10) <= ?
    `,
    )
    .get(start, end) as Record<string, unknown> | undefined;
  return Number(row?.v ?? 0);
}

function sumExpensesBetween(db: DatabaseSync, start: string, end: string, phase?: string): number {
  if (start > end || !tableExists(db, 'crm_svc_expenses')) return 0;
  if (phase) {
    const row = db
      .prepare(
        `
        SELECT COALESCE(SUM(amount_vnd), 0) AS v FROM crm_svc_expenses
        WHERE substr(expense_on, 1, 10) >= ? AND substr(expense_on, 1, 10) <= ?
          AND COALESCE(cost_phase, 'delivery') = ?
      `,
      )
      .get(start, end, phase) as Record<string, unknown> | undefined;
    return Number(row?.v ?? 0);
  }
  const row = db
    .prepare(
      `
      SELECT COALESCE(SUM(amount_vnd), 0) AS v FROM crm_svc_expenses
      WHERE substr(expense_on, 1, 10) >= ? AND substr(expense_on, 1, 10) <= ?
    `,
    )
    .get(start, end) as Record<string, unknown> | undefined;
  return Number(row?.v ?? 0);
}

function proxyCashPosition(db: DatabaseSync, asOf: string): number {
  if (!tableExists(db, 'crm_svc_payments') || !tableExists(db, 'crm_svc_expenses')) return 0;
  const recv = db
    .prepare(
      "SELECT COALESCE(SUM(amount_vnd), 0) AS v FROM crm_svc_payments WHERE status = 'received' AND substr(received_on, 1, 10) <= ?",
    )
    .get(asOf) as Record<string, unknown> | undefined;
  const exp = db
    .prepare("SELECT COALESCE(SUM(amount_vnd), 0) AS v FROM crm_svc_expenses WHERE substr(expense_on, 1, 10) <= ?")
    .get(asOf) as Record<string, unknown> | undefined;
  return Number(recv?.v ?? 0) - Number(exp?.v ?? 0);
}

export function getCashSnapshotOnOrBefore(db: DatabaseSync, asOf: string): Record<string, unknown> | null {
  ensureCashLedgerSchema(db);
  const row = db
    .prepare(
      `
      SELECT id, snapshot_on, balance_vnd, source, notes, updated_at
      FROM crm_owner_cash_snapshots
      WHERE snapshot_on <= ?
      ORDER BY snapshot_on DESC
      LIMIT 1
    `,
    )
    .get(asOf) as Record<string, unknown> | undefined;
  if (!row) return null;
  return {
    id: Number(row.id),
    snapshot_on: String(row.snapshot_on),
    balance_vnd: Number(row.balance_vnd ?? 0),
    source: String(row.source ?? CASH_SOURCE_MANUAL),
    notes: String(row.notes ?? ''),
    updated_at: String(row.updated_at ?? ''),
  };
}

export function listCashSnapshots(db: DatabaseSync, limit = 24): Record<string, unknown>[] {
  ensureCashLedgerSchema(db);
  const rows = db
    .prepare(
      `
      SELECT id, snapshot_on, balance_vnd, source, notes, updated_at
      FROM crm_owner_cash_snapshots
      ORDER BY snapshot_on DESC
      LIMIT ?
    `,
    )
    .all(Math.max(1, limit)) as Array<Record<string, unknown>>;
  return rows.map((r) => ({
    id: Number(r.id),
    snapshot_on: String(r.snapshot_on),
    balance_vnd: Number(r.balance_vnd ?? 0),
    source: String(r.source ?? CASH_SOURCE_MANUAL),
    notes: String(r.notes ?? ''),
    updated_at: String(r.updated_at ?? ''),
  }));
}

export function upsertCashSnapshot(
  db: DatabaseSync,
  snapshotOn: string,
  balanceVnd: number,
  source = CASH_SOURCE_MANUAL,
  notes = '',
): Record<string, unknown> {
  ensureCashLedgerSchema(db);
  const snap = parseYmd(snapshotOn);
  if (!snap) throw new Error('snapshot_on không hợp lệ (YYYY-MM-DD).');
  let src = String(source || CASH_SOURCE_MANUAL).trim().toLowerCase();
  if (!CASH_SOURCES.has(src)) src = CASH_SOURCE_MANUAL;
  const ts = new Date().toISOString().replace('T', ' ').slice(0, 19);
  db.prepare(
    `
    INSERT INTO crm_owner_cash_snapshots (snapshot_on, balance_vnd, source, notes, updated_at)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(snapshot_on) DO UPDATE SET
      balance_vnd = excluded.balance_vnd,
      source = excluded.source,
      notes = excluded.notes,
      updated_at = excluded.updated_at
  `,
  ).run(snap, Math.trunc(balanceVnd), src, String(notes || '').trim(), ts);
  const row = db
    .prepare(
      'SELECT id, snapshot_on, balance_vnd, source, notes, updated_at FROM crm_owner_cash_snapshots WHERE snapshot_on = ?',
    )
    .get(snap) as Record<string, unknown>;
  return {
    id: Number(row.id),
    snapshot_on: String(row.snapshot_on),
    balance_vnd: Number(row.balance_vnd ?? 0),
    source: String(row.source ?? CASH_SOURCE_MANUAL),
    notes: String(row.notes ?? ''),
    updated_at: String(row.updated_at ?? ''),
  };
}

export function deleteCashSnapshot(db: DatabaseSync, snapshotOn: string): boolean {
  ensureCashLedgerSchema(db);
  const snap = parseYmd(snapshotOn);
  if (!snap) throw new Error('snapshot_on không hợp lệ.');
  const result = db.prepare('DELETE FROM crm_owner_cash_snapshots WHERE snapshot_on = ?').run(snap);
  return Number(result.changes ?? 0) > 0;
}

export function getCashPosition(db: DatabaseSync, asOf: string): Record<string, unknown> {
  const snapshot = getCashSnapshotOnOrBefore(db, asOf);
  if (!snapshot) {
    return {
      as_of: asOf,
      position_vnd: proxyCashPosition(db, asOf),
      source: POSITION_SOURCE_PROXY,
      snapshot: null,
      flow_adjustment_vnd: 0,
    };
  }
  const snapOn = String(snapshot.snapshot_on);
  const base = Number(snapshot.balance_vnd);
  if (snapOn >= asOf) {
    return {
      as_of: asOf,
      position_vnd: base,
      source: POSITION_SOURCE_LEDGER,
      snapshot,
      flow_adjustment_vnd: 0,
    };
  }
  const flowStart = addDays(snapOn, 1);
  const cashIn = sumReceivedBetween(db, flowStart, asOf);
  const cashOut = sumExpensesBetween(db, flowStart, asOf);
  const adjustment = cashIn - cashOut;
  return {
    as_of: asOf,
    position_vnd: base + adjustment,
    source: POSITION_SOURCE_LEDGER,
    snapshot,
    flow_adjustment_vnd: adjustment,
    flow_cash_in_vnd: cashIn,
    flow_cash_out_vnd: cashOut,
  };
}

export function getOwnerWeeklyTargets(db: DatabaseSync): Record<string, number> {
  ensureKpiConfigSchema(db);
  const rows = db
    .prepare("SELECT config_key, config_value FROM crm_finance_kpi_config WHERE config_key LIKE 'owner_%'")
    .all() as Array<Record<string, unknown>>;
  const dbMap: Record<string, string> = {};
  for (const r of rows) {
    const key = String(r.config_key).replace(/^owner_/, '');
    dbMap[key] = String(r.config_value);
  }
  const out: Record<string, number> = {};
  for (const [key, defaultVal] of Object.entries(OWNER_WEEKLY_TARGET_DEFAULTS)) {
    if (key in dbMap) {
      const raw = dbMap[key]!.trim();
      const parsed = Number.isInteger(defaultVal) ? parseInt(raw, 10) : parseFloat(raw);
      if (Number.isFinite(parsed)) {
        out[key] = parsed;
        continue;
      }
    }
    const envKey = OWNER_WEEKLY_ENV_KEYS[key];
    out[key] = envKey ? envNumber(envKey, defaultVal) : defaultVal;
  }
  return out;
}

export function setOwnerWeeklyTargets(db: DatabaseSync, updates: Record<string, unknown>): Record<string, number> {
  ensureKpiConfigSchema(db);
  const ts = new Date().toISOString().replace('T', ' ').slice(0, 19);
  for (const [key, value] of Object.entries(updates)) {
    if (!(key in OWNER_WEEKLY_TARGET_DEFAULTS)) continue;
    const defaultVal = OWNER_WEEKLY_TARGET_DEFAULTS[key]!;
    const val = Number.isInteger(defaultVal) ? Math.max(0, Math.trunc(Number(value))) : Number(value);
    db.prepare(
      `
      INSERT INTO crm_finance_kpi_config (config_key, config_value, updated_at)
      VALUES (?, ?, ?)
      ON CONFLICT(config_key) DO UPDATE SET
        config_value = excluded.config_value,
        updated_at = excluded.updated_at
    `,
    ).run(`owner_${key}`, String(val), ts);
  }
  return getOwnerWeeklyTargets(db);
}

function ragHigherBetter(value: number, target: number): string {
  if (value >= target) return RAG_GREEN;
  if (value >= target * 0.85) return RAG_YELLOW;
  return RAG_RED;
}

function ragLowerBetter(value: number, target: number): string {
  if (value <= target) return RAG_GREEN;
  if (value <= target * 1.15) return RAG_YELLOW;
  return RAG_RED;
}

function metric(opts: Record<string, unknown>): Record<string, unknown> {
  return {
    status_label: RAG_LABELS[String(opts.status)] ?? String(opts.status),
    format: opts.fmt ?? 'number',
    ...opts,
  };
}

function buildPreExecutionBrief(dashboard: Record<string, unknown>): Record<string, unknown> {
  const actions: Record<string, unknown>[] = [];
  const blocks = dashboard.blocks as Record<string, Record<string, unknown>>;
  for (const blockKey of BLOCK_KEYS) {
    const block = blocks[blockKey];
    if (!block) continue;
    for (const m of (block.metrics as Record<string, unknown>[]) ?? []) {
      const status = String(m.status ?? RAG_GREEN);
      if (status === RAG_GREEN) continue;
      actions.push({
        metric_key: m.key,
        metric_label: m.label,
        block: blockKey,
        block_label: block.label,
        status,
        status_label: m.status_label,
        hint: m.note ?? '',
        steps: [],
      });
    }
  }
  return {
    actions,
    action_count: actions.length,
    red_count: actions.filter((a) => a.status === RAG_RED).length,
    yellow_count: actions.filter((a) => a.status === RAG_YELLOW).length,
  };
}

export function getOwnerWeeklyDashboard(
  db: DatabaseSync,
  opts: { weekEnd?: string | null; year?: number | null; isoWeek?: number | null; trendWeeks?: number },
): Record<string, unknown> {
  const bounds = resolveWeekBounds(opts);
  const { start, end, isoYear, isoWeek: isoWeekNum } = bounds;
  const targets = getOwnerWeeklyTargets(db);

  const cashCloseMeta = getCashPosition(db, end);
  const cashClose = Number(cashCloseMeta.position_vnd ?? 0);
  const cashIn = sumReceivedBetween(db, start, end);
  const cashOut = sumExpensesBetween(db, start, end);
  const ar = getArAging(db, { asOf: end });
  const arOverdue = Number(ar.total_overdue_vnd ?? 0);

  const recvWeek = cashIn;
  const delWeek = sumExpensesBetween(db, start, end, COST_PHASE_DELIVERY);
  const presalesWeek = sumExpensesBetween(db, start, end, COST_PHASE_PRESALES);
  const grossMargin = recvWeek > 0 ? Math.round(((recvWeek - delWeek) / recvWeek) * 1000) / 10 : 0;
  const netMargin =
    recvWeek > 0 ? Math.round(((recvWeek - delWeek - presalesWeek) / recvWeek) * 1000) / 10 : 0;

  const cashMetrics = [
    metric({
      key: 'cash_close',
      label: 'Tiền cuối tuần',
      value: cashClose,
      fmt: 'vnd',
      status: ragHigherBetter(cashClose, targets.cash_safe_min_vnd!),
      target: targets.cash_safe_min_vnd,
    }),
    metric({
      key: 'cash_in',
      label: 'Thu tuần',
      value: cashIn,
      fmt: 'vnd',
      status: ragHigherBetter(cashIn, targets.revenue_target_vnd!),
      target: targets.revenue_target_vnd,
    }),
    metric({
      key: 'ar_overdue',
      label: 'AR quá hạn',
      value: arOverdue,
      fmt: 'vnd',
      status: ragLowerBetter(arOverdue, targets.ar_overdue_max_vnd!),
      target: targets.ar_overdue_max_vnd,
    }),
  ];

  const salesMetrics = [
    metric({
      key: 'revenue_actual',
      label: 'Doanh thu tuần',
      value: recvWeek,
      fmt: 'vnd',
      status: ragHigherBetter(recvWeek, targets.revenue_target_vnd!),
      target: targets.revenue_target_vnd,
    }),
    metric({
      key: 'win_rate',
      label: 'Win rate (tuần)',
      value: 0,
      fmt: 'pct',
      status: RAG_GREEN,
      target: targets.close_rate_target_pct,
      note: 'MVP — simplified',
    }),
  ];

  const efficiencyMetrics = [
    metric({
      key: 'gross_margin',
      label: 'Gross margin',
      value: grossMargin,
      fmt: 'pct',
      status: ragHigherBetter(grossMargin, targets.gross_margin_target_pct!),
      target: targets.gross_margin_target_pct,
    }),
    metric({
      key: 'net_margin',
      label: 'Net margin',
      value: netMargin,
      fmt: 'pct',
      status: ragHigherBetter(netMargin, targets.net_margin_target_pct!),
      target: targets.net_margin_target_pct,
    }),
  ];

  const riskMetrics = [
    metric({
      key: 'top_customer_share',
      label: 'Tỷ trọng DT khách lớn nhất',
      value: 0,
      fmt: 'pct',
      status: RAG_GREEN,
      target: targets.top1_share_max_pct,
      note: 'MVP — simplified',
    }),
  ];

  const blocks: Record<string, Record<string, unknown>> = {
    cash: { key: 'cash', label: BLOCK_LABELS.cash, metrics: cashMetrics },
    sales: { key: 'sales', label: BLOCK_LABELS.sales, metrics: salesMetrics },
    efficiency: { key: 'efficiency', label: BLOCK_LABELS.efficiency, metrics: efficiencyMetrics },
    risk: { key: 'risk', label: BLOCK_LABELS.risk, metrics: riskMetrics },
  };

  const allMetrics = BLOCK_KEYS.flatMap((k) => (blocks[k]?.metrics as Record<string, unknown>[]) ?? []);
  const ragCounts = {
    [RAG_GREEN]: allMetrics.filter((m) => m.status === RAG_GREEN).length,
    [RAG_YELLOW]: allMetrics.filter((m) => m.status === RAG_YELLOW).length,
    [RAG_RED]: allMetrics.filter((m) => m.status === RAG_RED).length,
  };

  const dashboard: Record<string, unknown> = {
    week: {
      iso_year: isoYear,
      iso_week: isoWeekNum,
      start,
      end,
      label: `Tuần ${isoWeekNum}/${isoYear} (${formatDdMm(start)} – ${formatDdMm(end)})`,
    },
    blocks,
    targets,
    rag_counts: ragCounts,
    rag_legend: RAG_LABELS,
    cash_ledger: {
      position_source: cashCloseMeta.source,
      has_snapshot: cashCloseMeta.source === POSITION_SOURCE_LEDGER,
      latest_snapshot: cashCloseMeta.snapshot,
      snapshots: listCashSnapshots(db, 8),
      forecast: { forecast_vnd: cashClose, as_of: end, method: 'mvp_stub' },
    },
    trends: { weeks: opts.trendWeeks ?? 8, labels: [], cash_close_vnd: [] },
    retention_weekly: { customer_churn_pct: 0 },
  };
  dashboard.pre_execution = buildPreExecutionBrief(dashboard);
  return dashboard;
}

export function getOwnerWeeklyInboxSummary(db: DatabaseSync): Record<string, unknown> {
  if (!tableExists(db, 'crm_reminders')) {
    return { pending_count: 0, critical_count: 0, warning_count: 0, items: [] };
  }
  const rows = db
    .prepare(
      `
      SELECT id, title, body, remind_at, status, meta_json
      FROM crm_reminders
      WHERE scope = 'owner_weekly' AND reminder_kind = 'owner_weekly_alert' AND status = 'pending'
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
      iso_year: meta.iso_year,
      iso_week: meta.iso_week,
      metric_key: meta.metric_key,
    });
  }
  return { pending_count: items.length, critical_count: critical, warning_count: warning, items };
}

export function syncOwnerWeeklyInboxStub(
  db: DatabaseSync,
  isoYear: number,
  isoWeek: number,
  dashboard?: Record<string, unknown>,
): Record<string, unknown> {
  const dash = dashboard ?? getOwnerWeeklyDashboard(db, { year: isoYear, isoWeek });
  const brief = dash.pre_execution as Record<string, unknown>;
  return {
    iso_year: isoYear,
    iso_week: isoWeek,
    period_ref: isoYear * 100 + isoWeek,
    synced: Number(brief.action_count ?? 0),
    removed: 0,
    action_count: Number(brief.action_count ?? 0),
    red_count: Number(brief.red_count ?? 0),
    yellow_count: Number(brief.yellow_count ?? 0),
    stub: true,
  };
}
