import { ServiceUnavailableException } from '@nestjs/common';
import {
  defaultBusinessPlan,
  defaultMarketingPlan,
  defaultSalesPlan,
} from './re-projects-plan.util';
import { ReProjectsAccountingRepository } from './re-projects-accounting.repository';
import { ReProjectsSqliteRepository } from './re-projects-sqlite.repository';
import {
  BUDGET_CATEGORIES,
  BUDGET_CATEGORY_LABELS,
  ReProjectRow,
  RISK_LEVEL_LABELS,
  SaveCashFlowBody,
} from './re-projects.types';

export const CASH_FLOW_TYPES = ['inflow', 'outflow'] as const;
export const CASH_FLOW_TYPE_LABELS: Record<string, string> = { inflow: 'Thu', outflow: 'Chi' };

export const CASH_FLOW_STATUSES = ['planned', 'confirmed', 'paid', 'cancelled'] as const;
export const CASH_FLOW_STATUS_LABELS: Record<string, string> = {
  planned: 'Kế hoạch',
  confirmed: 'Đã xác nhận',
  paid: 'Đã thanh toán',
  cancelled: 'Đã hủy',
};

export const CASH_FLOW_SOURCES = ['manual', 'plan_sync', 'inventory', 'import'] as const;
export const CASH_FLOW_SOURCE_LABELS: Record<string, string> = {
  manual: 'Nhập tay',
  plan_sync: 'Đồng bộ KH',
  inventory: 'Tồn kho',
  import: 'Import CSV',
};

export const MARKETING_SUB_CATEGORY_LABELS: Record<string, string> = {
  fb_ads: 'Facebook / Meta Ads',
  google_ads: 'Google Ads',
  zalo_ads: 'Zalo Ads',
  tiktok_ads: 'TikTok Ads',
  event: 'Sự kiện / Activation',
  content: 'Content / Sáng tạo',
  agency: 'Agency / Dịch vụ',
  influencer: 'KOL / Influencer',
  ooh: 'OOH / Bảng quảng cáo',
  other: 'Khác',
};

export interface AccountingDeps {
  accounting: ReProjectsAccountingRepository;
  projects: ReProjectsSqliteRepository;
}

function norm(text: string): string {
  let s = String(text ?? '').toLowerCase();
  s = s.replace(/[àáạảãâầấậẩẫăằắặẳẵ]/g, 'a');
  s = s.replace(/[èéẹẻẽêềếệểễ]/g, 'e');
  s = s.replace(/[ìíịỉĩ]/g, 'i');
  s = s.replace(/[òóọỏõôồốộổỗơờớợởỡ]/g, 'o');
  s = s.replace(/[ùúụủũưừứựửữ]/g, 'u');
  s = s.replace(/[ỳýỵỷỹ]/g, 'y');
  s = s.replace(/[đ]/g, 'd');
  return s;
}

function fmtVnd(n: number): string {
  return `${Math.trunc(n)}`.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
}

export function ensureAccountingSchema(deps: AccountingDeps): void {
  deps.accounting.ensureAccountingSchema();
}

function cashFlowRow(row: Record<string, unknown>): Record<string, unknown> {
  let ft = String(row.flow_type ?? 'outflow');
  if (!(CASH_FLOW_TYPES as readonly string[]).includes(ft)) ft = 'outflow';
  let st = String(row.status ?? 'planned');
  if (!(CASH_FLOW_STATUSES as readonly string[]).includes(st)) st = 'planned';
  const cat = String(row.category ?? 'other');
  const sub = String(row.sub_category ?? '');
  const src = String(row.source_type ?? 'manual');
  return {
    id: Number(row.id),
    project_id: Number(row.project_id),
    flow_type: ft,
    flow_type_label: CASH_FLOW_TYPE_LABELS[ft] ?? ft,
    category: cat,
    category_label: BUDGET_CATEGORY_LABELS[cat] ?? cat,
    sub_category: sub,
    sub_category_label: sub ? (MARKETING_SUB_CATEGORY_LABELS[sub] ?? sub) : '',
    line_item: String(row.line_item ?? ''),
    amount_vnd: Number(row.amount_vnd ?? 0),
    period_month: String(row.period_month ?? ''),
    transaction_date: String(row.transaction_date ?? ''),
    due_date: String(row.due_date ?? ''),
    paid_date: String(row.paid_date ?? ''),
    status: st,
    status_label: CASH_FLOW_STATUS_LABELS[st] ?? st,
    source_type: src,
    source_type_label: CASH_FLOW_SOURCE_LABELS[src] ?? src,
    source_ref: String(row.source_ref ?? ''),
    counterparty: String(row.counterparty ?? ''),
    notes: String(row.notes ?? ''),
    created_by: String(row.created_by ?? ''),
    created_at: String(row.created_at ?? ''),
    updated_at: String(row.updated_at ?? ''),
  };
}

export function listCashFlowLines(
  deps: AccountingDeps,
  projectId: number,
  filters: { flow_type?: string; category?: string; status?: string } = {},
): Array<Record<string, unknown>> {
  ensureAccountingSchema(deps);
  const clauses: string[] = [];
  const params: string[] = [];
  if (filters.flow_type && (CASH_FLOW_TYPES as readonly string[]).includes(filters.flow_type)) {
    clauses.push('AND flow_type = ?');
    params.push(filters.flow_type);
  }
  if (filters.category && (BUDGET_CATEGORIES as readonly string[]).includes(filters.category as never)) {
    clauses.push('AND category = ?');
    params.push(filters.category);
  }
  if (filters.status && (CASH_FLOW_STATUSES as readonly string[]).includes(filters.status as never)) {
    clauses.push('AND status = ?');
    params.push(filters.status);
  }
  const rows = deps.accounting.queryCashFlowRows(projectId, clauses.join(' '), params);
  return rows.map(cashFlowRow);
}

export function saveCashFlowLine(
  deps: AccountingDeps,
  projectId: number,
  payload: SaveCashFlowBody,
  opts: { lineId?: number; createdBy?: string; ts?: string } = {},
): Record<string, unknown> {
  ensureAccountingSchema(deps);
  const tsVal = opts.ts ?? deps.accounting.nowTs();
  const item = String(payload.line_item ?? '').trim();
  if (!item) throw new Error('Thiếu mô tả dòng tiền.');
  let ft = String(payload.flow_type ?? 'outflow');
  if (!(CASH_FLOW_TYPES as readonly string[]).includes(ft)) ft = 'outflow';
  let cat = String(payload.category ?? 'other');
  if (!(BUDGET_CATEGORIES as readonly string[]).includes(cat as never)) cat = 'other';
  let st = String(payload.status ?? 'planned');
  if (!(CASH_FLOW_STATUSES as readonly string[]).includes(st as never)) st = 'planned';
  let src = String(payload.source_type ?? 'manual');
  if (!(CASH_FLOW_SOURCES as readonly string[]).includes(src as never)) src = 'manual';
  const amount = Math.max(0, Number(payload.amount_vnd ?? 0));

  const fields = [
    ft,
    cat,
    String(payload.sub_category ?? '').slice(0, 40),
    item.slice(0, 200),
    amount,
    String(payload.period_month ?? '').slice(0, 7),
    String(payload.transaction_date ?? '').slice(0, 10),
    String(payload.due_date ?? '').slice(0, 10),
    String(payload.paid_date ?? '').slice(0, 10),
    st,
    src,
    String(payload.source_ref ?? '').slice(0, 120),
    String(payload.counterparty ?? '').slice(0, 120),
    String(payload.notes ?? '').slice(0, 2000),
  ];

  let rid: number;
  if (opts.lineId) {
    deps.accounting.updateCashFlowLine(projectId, opts.lineId, fields, tsVal);
    rid = opts.lineId;
  } else {
    rid = deps.accounting.insertCashFlowLine(
      projectId,
      [...fields, String(opts.createdBy ?? '').slice(0, 80)],
      tsVal,
    );
  }
  const row = deps.accounting.getCashFlowRow(rid);
  if (!row) throw new Error('Không lưu được dòng tiền.');
  return cashFlowRow(row);
}

export function deleteCashFlowLine(deps: AccountingDeps, projectId: number, lineId: number): void {
  ensureAccountingSchema(deps);
  deps.accounting.deleteCashFlowLine(projectId, lineId);
}

export function syncBudgetFromPlans(
  deps: AccountingDeps,
  projectId: number,
  ts?: string,
): Record<string, number> {
  const proj = deps.projects.fetchProject(projectId);
  if (!proj) throw new Error('Không tìm thấy dự án.');
  const tsVal = ts ?? deps.accounting.nowTs();
  const bp = proj.business_plan ?? defaultBusinessPlan();
  const mp = proj.marketing_plan ?? defaultMarketingPlan();
  const sp = proj.sales_plan ?? defaultSalesPlan();
  const fp = (bp.financial_plan as Record<string, unknown>) ?? {};
  let created = 0;
  let updated = 0;
  let skipped = 0;

  const seeds: Array<[string, string, number, string, string]> = [
    ['revenue', 'Doanh thu mục tiêu (KH kinh doanh)', Number(bp.revenue_target_vnd ?? 0), 'plan:business:revenue', ''],
    ['revenue', 'Doanh thu mục tiêu (KH bán hàng)', Number(sp.revenue_target_vnd ?? 0), 'plan:sales:revenue', ''],
    ['cogs', 'Chi phí đất (KH tài chính)', Number(fp.land_cost_vnd ?? 0), 'plan:financial:land', ''],
    ['cogs', 'Chi phí xây dựng (KH tài chính)', Number(fp.construction_cost_vnd ?? 0), 'plan:financial:construction', ''],
    ['marketing', 'Marketing (KH tài chính)', Number(fp.marketing_cost_vnd ?? 0), 'plan:financial:marketing', ''],
    ['sales', 'Chi phí bán hàng (KH tài chính)', Number(fp.sales_cost_vnd ?? 0), 'plan:financial:sales', ''],
    ['marketing', 'Ngân sách MKT tổng (KH marketing)', Number(mp.budget_total_vnd ?? 0), 'plan:marketing:total', ''],
  ];

  for (const [cat, label, amount, ref, sub] of seeds) {
    if (amount <= 0) {
      skipped += 1;
      continue;
    }
    const [action] = deps.accounting.upsertBudgetByRef(
      projectId,
      { category: cat, lineItem: label, plannedVnd: amount, sourceRef: ref, subCategory: sub },
      tsVal,
    );
    if (action === 'created') created += 1;
    else if (action === 'updated') updated += 1;
    else skipped += 1;
  }

  const breakdown = (mp.budget_breakdown as Array<Record<string, unknown>>) ?? [];
  breakdown.forEach((row, i) => {
    if (!row || typeof row !== 'object') return;
    const channel = String(row.channel ?? row.name ?? `Kênh ${i + 1}`).slice(0, 80);
    const amount = Number(row.amount_vnd ?? row.budget_vnd ?? 0);
    if (amount <= 0) return;
    const sub = String(row.sub_category ?? 'other').slice(0, 40);
    const ref = `plan:marketing:breakdown:${i}:${norm(channel).slice(0, 30)}`;
    const [action] = deps.accounting.upsertBudgetByRef(
      projectId,
      { category: 'marketing', lineItem: `MKT — ${channel}`, plannedVnd: amount, sourceRef: ref, subCategory: sub },
      tsVal,
    );
    if (action === 'created') created += 1;
    else if (action === 'updated') updated += 1;
  });

  return { created, updated, skipped };
}

export function syncRevenueFromInventory(
  deps: AccountingDeps,
  projectId: number,
  opts: { ts?: string; createdBy?: string } = {},
): Record<string, unknown> {
  const products = deps.projects.listProducts(projectId);
  const sold = products.filter((p) => String(p.status ?? '') === 'sold');
  const total = sold.reduce(
    (s, p) => s + Number(p.net_price_vnd ?? p.list_price_vnd ?? 0),
    0,
  );
  const tsVal = opts.ts ?? deps.accounting.nowTs();
  const period = tsVal.slice(0, 7);

  const existing = deps.accounting.findBudgetBySourceRef(projectId, 'inventory:revenue');
  let budgetAction: string;
  if (existing) {
    deps.accounting.updateBudgetActual(
      projectId,
      Number(existing.id),
      total,
      `Doanh thu từ tồn kho (${sold.length} căn đã bán)`,
      tsVal,
    );
    budgetAction = 'updated';
  } else {
    deps.accounting.insertInventoryBudgetLine(
      projectId,
      `Doanh thu từ tồn kho (${sold.length} căn đã bán)`,
      period,
      total,
      tsVal,
    );
    budgetAction = 'created';
  }

  const cfExisting = deps.accounting.findCashFlowBySourceRef(projectId, 'inventory:revenue:inflow');
  const cfPayload: SaveCashFlowBody = {
    flow_type: 'inflow',
    category: 'revenue',
    line_item: `Thu từ bán hàng tồn kho (${sold.length} căn)`,
    amount_vnd: total,
    period_month: period,
    status: total > 0 ? 'confirmed' : 'planned',
    source_type: 'inventory',
    source_ref: 'inventory:revenue:inflow',
    notes: `Tự động từ ${sold.length} sản phẩm status=sold`,
  };

  let cashAction: string;
  if (cfExisting) {
    saveCashFlowLine(deps, projectId, cfPayload, {
      lineId: Number(cfExisting.id),
      createdBy: opts.createdBy,
      ts: tsVal,
    });
    cashAction = 'updated';
  } else if (total > 0) {
    saveCashFlowLine(deps, projectId, cfPayload, { createdBy: opts.createdBy, ts: tsVal });
    cashAction = 'created';
  } else {
    cashAction = 'skipped';
  }

  return {
    sold_units: sold.length,
    revenue_vnd: total,
    budget_action: budgetAction,
    cash_flow_action: cashAction,
  };
}

function parseCsvRows(csvText: string): Array<Record<string, string>> {
  const text = csvText.replace(/^\ufeff/, '');
  const lines = text.split(/\r?\n/).filter((l) => l.trim());
  if (!lines.length) return [];
  const parseLine = (line: string): string[] => {
    const out: string[] = [];
    let cur = '';
    let inQuotes = false;
    for (let i = 0; i < line.length; i += 1) {
      const ch = line[i];
      if (ch === '"') {
        if (inQuotes && line[i + 1] === '"') {
          cur += '"';
          i += 1;
        } else {
          inQuotes = !inQuotes;
        }
      } else if (ch === ',' && !inQuotes) {
        out.push(cur);
        cur = '';
      } else {
        cur += ch;
      }
    }
    out.push(cur);
    return out;
  };
  const headers = parseLine(lines[0]).map((h) => h.trim());
  return lines.slice(1).map((line) => {
    const vals = parseLine(line);
    const row: Record<string, string> = {};
    headers.forEach((h, i) => {
      row[h] = vals[i] ?? '';
    });
    return row;
  });
}

export function importCashFlowCsv(
  deps: AccountingDeps,
  projectId: number,
  csvText: string,
  opts: { createdBy?: string; ts?: string } = {},
): Record<string, number> {
  ensureAccountingSchema(deps);
  const tsVal = opts.ts ?? deps.accounting.nowTs();
  let created = 0;
  let updated = 0;
  let errors = 0;

  for (const row of parseCsvRows(csvText)) {
    try {
      const ftRaw = String(row.flow_type ?? row.loai ?? 'outflow')
        .trim()
        .toLowerCase();
      const ft = ['inflow', 'thu', 'in'].includes(ftRaw) ? 'inflow' : 'outflow';
      let cat = String(row.category ?? row.hang_muc ?? 'other')
        .trim()
        .toLowerCase();
      if (!(BUDGET_CATEGORIES as readonly string[]).includes(cat as never)) {
        cat = cat.includes('mkt') || cat.includes('marketing') ? 'marketing' : 'other';
      }
      const item = String(row.line_item ?? row.mo_ta ?? row.description ?? '').trim();
      if (!item) {
        errors += 1;
        continue;
      }
      const amount = Math.trunc(
        Number(String(row.amount_vnd ?? row.so_tien ?? '0').replace(/,/g, '') || 0),
      );
      const payload: SaveCashFlowBody = {
        flow_type: ft,
        category: cat,
        sub_category: String(row.sub_category ?? row.kenh ?? '').slice(0, 40),
        line_item: item,
        amount_vnd: amount,
        period_month: String(row.period_month ?? row.ky ?? '').slice(0, 7),
        transaction_date: String(row.transaction_date ?? row.ngay ?? '').slice(0, 10),
        status: String(row.status ?? 'planned').trim().toLowerCase() || 'planned',
        counterparty: String(row.counterparty ?? row.doi_tac ?? '').slice(0, 120),
        notes: String(row.notes ?? row.ghi_chu ?? '').slice(0, 2000),
        source_type: 'import',
      };
      const ref = String(row.source_ref ?? row.ma ?? '').trim();
      if (ref) {
        payload.source_ref = ref;
        const ex = deps.accounting.findCashFlowBySourceRef(projectId, ref);
        if (ex) {
          saveCashFlowLine(deps, projectId, payload, {
            lineId: Number(ex.id),
            createdBy: opts.createdBy,
            ts: tsVal,
          });
          updated += 1;
          continue;
        }
      }
      saveCashFlowLine(deps, projectId, payload, { createdBy: opts.createdBy, ts: tsVal });
      created += 1;
    } catch {
      errors += 1;
    }
  }
  return { created, updated, errors };
}

export function computeAccountingDashboard(
  deps: AccountingDeps,
  projectId: number,
): Record<string, unknown> {
  const budget = deps.projects.listBudgetLines(projectId);
  const cash = listCashFlowLines(deps, projectId);
  const products = deps.projects.listProducts(projectId);
  const sold = products.filter((p) => p.status === 'sold');
  const inventoryRevenue = sold.reduce(
    (s, p) => s + Number(p.net_price_vnd ?? p.list_price_vnd ?? 0),
    0,
  );

  const pnlByCategory: Record<string, Record<string, unknown>> = {};
  for (const cat of BUDGET_CATEGORIES) {
    const lines = budget.filter((b) => b.category === cat);
    const pl = lines.reduce((s, b) => s + Number(b.planned_vnd ?? 0), 0);
    const ac = lines.reduce((s, b) => s + Number(b.actual_vnd ?? 0), 0);
    pnlByCategory[cat] = {
      category: cat,
      category_label: BUDGET_CATEGORY_LABELS[cat] ?? cat,
      planned_vnd: pl,
      actual_vnd: ac,
      variance_vnd: ac - pl,
    };
  }

  const revPl = Number(pnlByCategory.revenue?.planned_vnd ?? 0);
  const revAc = Number(pnlByCategory.revenue?.actual_vnd ?? 0);
  const costPl = Object.entries(pnlByCategory)
    .filter(([k]) => k !== 'revenue')
    .reduce((s, [, v]) => s + Number(v.planned_vnd ?? 0), 0);
  const costAc = Object.entries(pnlByCategory)
    .filter(([k]) => k !== 'revenue')
    .reduce((s, [, v]) => s + Number(v.actual_vnd ?? 0), 0);

  const sumCash = (flowType: string, statuses: string[]) =>
    cash
      .filter((c) => c.flow_type === flowType && statuses.includes(String(c.status)))
      .reduce((s, c) => s + Number(c.amount_vnd ?? 0), 0);

  const inflowPaid = sumCash('inflow', ['paid']);
  const inflowConfirmed = sumCash('inflow', ['confirmed', 'paid']);
  const outflowPaid = sumCash('outflow', ['paid']);
  const outflowConfirmed = sumCash('outflow', ['confirmed', 'paid']);
  const inflowPlanned = sumCash('inflow', ['planned', 'confirmed', 'paid']);
  const outflowPlanned = sumCash('outflow', ['planned', 'confirmed', 'paid']);

  const marketingCash = cash.filter((c) => c.category === 'marketing' && c.flow_type === 'outflow');
  const marketingBySub: Record<string, Record<string, unknown>> = {};
  for (const c of marketingCash) {
    const sub = String(c.sub_category ?? 'other');
    if (!marketingBySub[sub]) {
      marketingBySub[sub] = {
        sub_category: sub,
        sub_category_label: (MARKETING_SUB_CATEGORY_LABELS[sub] ?? sub) || 'Khác',
        planned_vnd: 0,
        paid_vnd: 0,
        total_vnd: 0,
      };
    }
    const bucket = marketingBySub[sub];
    const amt = Number(c.amount_vnd ?? 0);
    bucket.total_vnd = Number(bucket.total_vnd) + amt;
    if (['planned', 'confirmed'].includes(String(c.status))) {
      bucket.planned_vnd = Number(bucket.planned_vnd) + amt;
    }
    if (c.status === 'paid') bucket.paid_vnd = Number(bucket.paid_vnd) + amt;
  }

  const mktBudgetPl = Number(pnlByCategory.marketing?.planned_vnd ?? 0);
  const mktBudgetAc = Number(pnlByCategory.marketing?.actual_vnd ?? 0);
  const mktCashPaid = Object.values(marketingBySub).reduce((s, b) => s + Number(b.paid_vnd ?? 0), 0);
  const mktCashTotal = Object.values(marketingBySub).reduce((s, b) => s + Number(b.total_vnd ?? 0), 0);

  const monthly: Record<string, { inflow_vnd: number; outflow_vnd: number; net_vnd: number }> = {};
  for (const c of cash) {
    if (c.status === 'cancelled') continue;
    const mo = String(c.period_month ?? c.transaction_date ?? '').slice(0, 7) || '—';
    if (!monthly[mo]) monthly[mo] = { inflow_vnd: 0, outflow_vnd: 0, net_vnd: 0 };
    const amt = Number(c.amount_vnd ?? 0);
    if (c.flow_type === 'inflow') monthly[mo].inflow_vnd += amt;
    else monthly[mo].outflow_vnd += amt;
    monthly[mo].net_vnd = monthly[mo].inflow_vnd - monthly[mo].outflow_vnd;
  }

  const monthlyTrend = Object.entries(monthly)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([period_month, v]) => ({ period_month, ...v }));

  const roiDenominator = mktCashPaid || mktBudgetAc || mktBudgetPl;
  const marketingRoiPct = roiDenominator
    ? Math.round(((revAc - mktCashPaid) / roiDenominator) * 1000) / 10
    : 0;

  return {
    pnl: {
      revenue_planned_vnd: revPl,
      revenue_actual_vnd: revAc,
      cost_planned_vnd: costPl,
      cost_actual_vnd: costAc,
      profit_planned_vnd: revPl - costPl,
      profit_actual_vnd: revAc - costAc,
      by_category: Object.values(pnlByCategory),
    },
    cash_flow: {
      inflow_paid_vnd: inflowPaid,
      inflow_confirmed_vnd: inflowConfirmed,
      outflow_paid_vnd: outflowPaid,
      outflow_confirmed_vnd: outflowConfirmed,
      inflow_planned_vnd: inflowPlanned,
      outflow_planned_vnd: outflowPlanned,
      net_cash_paid_vnd: inflowPaid - outflowPaid,
      net_cash_confirmed_vnd: inflowConfirmed - outflowConfirmed,
      line_count: cash.length,
    },
    marketing: {
      budget_planned_vnd: mktBudgetPl,
      budget_actual_vnd: mktBudgetAc,
      cash_paid_vnd: mktCashPaid,
      cash_total_vnd: mktCashTotal,
      roi_pct: marketingRoiPct,
      by_channel: Object.values(marketingBySub).sort(
        (a, b) => Number(b.total_vnd ?? 0) - Number(a.total_vnd ?? 0),
      ),
    },
    inventory: {
      sold_units: sold.length,
      revenue_vnd: inventoryRevenue,
      available_units: products.filter((p) => p.status === 'available').length,
    },
    monthly_trend: monthlyTrend,
  };
}

function riskLevelFromScore(probabilityPct: number, impactPct: number): string {
  const score = (probabilityPct * impactPct) / 100;
  if (score >= 56) return 'critical';
  if (score >= 36) return 'high';
  if (score >= 16) return 'medium';
  return 'low';
}

function riskItem(data: {
  code: string;
  title: string;
  description: string;
  category?: string;
  probability_pct: number;
  impact_pct: number;
  recommendation: string;
  indicators?: string[];
}): Record<string, unknown> {
  const category = data.category ?? 'finance';
  const lv = riskLevelFromScore(data.probability_pct, data.impact_pct);
  const categoryLabels: Record<string, string> = {
    finance: 'Tài chính',
    sales: 'Bán hàng',
    market: 'Thị trường',
  };
  return {
    code: data.code,
    title: data.title,
    description: data.description,
    category,
    category_label: categoryLabels[category] ?? category,
    probability_pct: Math.round(data.probability_pct * 10) / 10,
    impact_pct: Math.round(data.impact_pct * 10) / 10,
    risk_level: lv,
    risk_level_label: RISK_LEVEL_LABELS[lv] ?? lv,
    score: Math.round((data.probability_pct * data.impact_pct) / 100 * 10) / 10,
    recommendation: data.recommendation,
    indicators: data.indicators ?? [],
  };
}

export function forecastFinancialOutlook(
  deps: AccountingDeps,
  projectId: number,
  opts: { monthsAhead?: number; dash?: Record<string, unknown> } = {},
): Record<string, unknown> {
  const monthsAhead = opts.monthsAhead ?? 3;
  const dash = opts.dash ?? computeAccountingDashboard(deps, projectId);
  const pnl = (dash.pnl as Record<string, unknown>) ?? {};
  const cf = (dash.cash_flow as Record<string, unknown>) ?? {};
  const trend = ((dash.monthly_trend as Array<Record<string, unknown>>) ?? []).filter(
    (t) => !['', '—'].includes(String(t.period_month ?? '')),
  );
  const recent = trend.slice(-3);
  const avgIn = recent.length
    ? Math.round(recent.reduce((s, t) => s + Number(t.inflow_vnd ?? 0), 0) / recent.length)
    : 0;
  const avgOut = recent.length
    ? Math.round(recent.reduce((s, t) => s + Number(t.outflow_vnd ?? 0), 0) / recent.length)
    : 0;
  const avgNet = avgIn - avgOut;

  const projections: Array<Record<string, unknown>> = [];
  const now = new Date();
  let y = now.getFullYear();
  let m = now.getMonth() + 1;
  for (let i = 1; i <= Math.max(1, monthsAhead); i += 1) {
    let nm = m + i;
    let ny = y + Math.floor((nm - 1) / 12);
    nm = ((nm - 1) % 12) + 1;
    const period = `${String(ny).padStart(4, '0')}-${String(nm).padStart(2, '0')}`;
    projections.push({
      period_month: period,
      projected_inflow_vnd: avgIn,
      projected_outflow_vnd: avgOut,
      projected_net_vnd: avgNet,
    });
  }

  const netCash = Number(cf.net_cash_paid_vnd ?? 0);
  let runwayMonths: number | null = null;
  if (avgNet < 0 && netCash > 0) runwayMonths = Math.round((netCash / Math.abs(avgNet)) * 10) / 10;
  else if (avgNet < 0 && netCash <= 0) runwayMonths = 0;

  const revGap = Math.max(
    0,
    Number(pnl.revenue_planned_vnd ?? 0) - Number(pnl.revenue_actual_vnd ?? 0),
  );
  const profitActual = Number(pnl.profit_actual_vnd ?? 0);
  const projectedProfit = profitActual + avgNet * monthsAhead;

  let outlook: string;
  let outlookLabel: string;
  if (avgNet < 0 && runwayMonths != null && runwayMonths < 2) {
    outlook = 'critical';
    outlookLabel = 'Nguy cơ cao — dòng tiền âm';
  } else if (avgNet < 0 || projectedProfit < 0) {
    outlook = 'at_risk';
    outlookLabel = 'Cần theo dõi — áp lực tài chính';
  } else if (revGap > Number(pnl.revenue_planned_vnd ?? 0) * 0.3) {
    outlook = 'neutral';
    outlookLabel = 'Ổn định nhưng chưa đạt DT KH';
  } else {
    outlook = 'positive';
    outlookLabel = 'Tích cực';
  }

  return {
    months_ahead: monthsAhead,
    avg_monthly_inflow_vnd: avgIn,
    avg_monthly_outflow_vnd: avgOut,
    avg_monthly_net_vnd: avgNet,
    projected_profit_vnd: projectedProfit,
    revenue_gap_vnd: revGap,
    runway_months: runwayMonths,
    outlook,
    outlook_label: outlookLabel,
    projections,
    data_points: recent.length,
  };
}

export function predictFinancialRisks(
  deps: AccountingDeps,
  projectId: number,
  opts: { dash?: Record<string, unknown> } = {},
): Record<string, unknown> {
  const proj = deps.projects.fetchProject(projectId);
  if (!proj) throw new Error('Không tìm thấy dự án.');
  const dash = opts.dash ?? computeAccountingDashboard(deps, projectId);
  const forecast = forecastFinancialOutlook(deps, projectId, { dash });
  const pnl = (dash.pnl as Record<string, unknown>) ?? {};
  const cf = (dash.cash_flow as Record<string, unknown>) ?? {};
  const mkt = (dash.marketing as Record<string, unknown>) ?? {};
  const inv = (dash.inventory as Record<string, unknown>) ?? {};
  const sp = proj.sales_plan ?? defaultSalesPlan();

  const revPl = Number(pnl.revenue_planned_vnd ?? 0);
  const revAc = Number(pnl.revenue_actual_vnd ?? 0);
  const costPl = Number(pnl.cost_planned_vnd ?? 0);
  const costAc = Number(pnl.cost_actual_vnd ?? 0);
  const profitPl = Number(pnl.profit_planned_vnd ?? 0);
  const profitAc = Number(pnl.profit_actual_vnd ?? 0);

  const risks: Array<Record<string, unknown>> = [];

  const netPaid = Number(cf.net_cash_paid_vnd ?? 0);
  if (netPaid < 0) {
    risks.push(
      riskItem({
        code: 'cash_negative',
        title: 'Dòng tiền ròng âm',
        description: `Dòng tiền đã thanh toán âm ${fmtVnd(Math.abs(netPaid))} VND — chi vượt thu.`,
        probability_pct: 85,
        impact_pct: 90,
        recommendation:
          'Rà soát chi phí không cần thiết, đẩy thu cọc/đợt thanh toán, hoãn chi MKT không hiệu quả.',
        indicators: [`Ròng TT: ${netPaid.toLocaleString('en-US')} VND`],
      }),
    );
  }

  const gapPlanned = Number(cf.inflow_planned_vnd ?? 0) - Number(cf.outflow_planned_vnd ?? 0);
  if (gapPlanned < 0) {
    risks.push(
      riskItem({
        code: 'cash_gap_planned',
        title: 'Thiếu hụt dòng tiền dự kiến',
        description: 'Tổng chi dự kiến vượt thu dự kiến trong sổ dòng tiền.',
        probability_pct: 70,
        impact_pct: 75,
        recommendation:
          'Lập lịch thu theo milestone bán hàng; đối soát cam kết chi với ngân sách đã duyệt.',
        indicators: [`Chênh thu-chi KH: ${gapPlanned.toLocaleString('en-US')} VND`],
      }),
    );
  }

  if (revPl > 0 && revAc < revPl * 0.65) {
    const pct = Math.round((1 - revAc / revPl) * 1000) / 10;
    risks.push(
      riskItem({
        code: 'revenue_shortfall',
        title: 'Doanh thu chậm so với kế hoạch',
        description: `DT thực tế chỉ đạt ${Math.round((revAc / revPl) * 1000) / 10}% kế hoạch (thiếu ~${pct}%).`,
        category: 'sales',
        probability_pct: Math.min(95, 50 + pct / 2),
        impact_pct: 80,
        recommendation:
          'Tăng tốc chốt deal, review giá/chính sách, đồng bộ KPI sales với tồn kho còn hàng.',
        indicators: [`DT KH: ${revPl.toLocaleString('en-US')}`, `DT TT: ${revAc.toLocaleString('en-US')}`],
      }),
    );
  }

  if (costPl > 0 && costAc > costPl * 1.12) {
    const over = Math.round((costAc / costPl - 1) * 1000) / 10;
    risks.push(
      riskItem({
        code: 'cost_overrun',
        title: 'Chi phí vượt ngân sách',
        description: `Chi phí thực tế vượt kế hoạch ~${over}%.`,
        probability_pct: Math.min(90, 40 + over),
        impact_pct: 70,
        recommendation:
          'Freeze chi không gắn doanh thu; phân loại COGS vs OPEX; báo cáo variance hàng tuần.',
        indicators: [`Chi KH: ${costPl.toLocaleString('en-US')}`, `Chi TT: ${costAc.toLocaleString('en-US')}`],
      }),
    );
  }

  const mktPl = Number(mkt.budget_planned_vnd ?? 0);
  const mktPaid = Number(mkt.cash_paid_vnd ?? 0);
  if (mktPl > 0 && mktPaid > mktPl * 1.1) {
    risks.push(
      riskItem({
        code: 'marketing_overspend',
        title: 'Chi marketing vượt ngân sách',
        description: `Đã chi MKT ${fmtVnd(mktPaid)} so với KH ${fmtVnd(mktPl)}.`,
        category: 'market',
        probability_pct: 75,
        impact_pct: 55,
        recommendation:
          'Tạm dừng kênh ROI thấp; A/B test creative; gắn chi MKT với CPL/CAC thực tế.',
        indicators: [`MKT chi TT: ${mktPaid.toLocaleString('en-US')}`, `MKT KH: ${mktPl.toLocaleString('en-US')}`],
      }),
    );
  }

  if (mktPaid > 0 && Number(mkt.roi_pct ?? 0) < 0) {
    risks.push(
      riskItem({
        code: 'marketing_negative_roi',
        title: 'ROI marketing âm',
        description: `ROI marketing ước tính ${mkt.roi_pct} — chi MKT chưa tạo DT tương xứng.`,
        category: 'market',
        probability_pct: 65,
        impact_pct: 60,
        recommendation:
          'Đo lại attribution lead→deal; tối ưu funnel trước khi tăng ngân sách quảng cáo.',
        indicators: [`ROI: ${mkt.roi_pct}%`],
      }),
    );
  }

  if (profitPl > 0 && profitAc < profitPl * 0.45) {
    risks.push(
      riskItem({
        code: 'profit_erosion',
        title: 'Lợi nhuận suy giảm so với KH',
        description: `LN thực tế ${fmtVnd(profitAc)} so với KH ${fmtVnd(profitPl)}.`,
        probability_pct: 70,
        impact_pct: 85,
        recommendation:
          'Phân tích biên lợi nhuận theo phân khu; điều chỉnh mix sản phẩm bán; kiểm soát chi cố định.',
        indicators: [`LN KH: ${profitPl.toLocaleString('en-US')}`, `LN TT: ${profitAc.toLocaleString('en-US')}`],
      }),
    );
  }

  const unitsTarget = Number(sp.units_target ?? 0);
  const sold = Number(inv.sold_units ?? 0);
  const totalUnits = Number(proj.total_units ?? 0);
  if (unitsTarget > 0 && sold < unitsTarget * 0.35) {
    risks.push(
      riskItem({
        code: 'sales_velocity_low',
        title: 'Tốc độ bán chậm',
        description: `Chỉ bán ${sold}/${unitsTarget} căn mục tiêu KH bán hàng.`,
        category: 'sales',
        probability_pct: 60,
        impact_pct: 75,
        recommendation:
          'Review pipeline lead, chính sách hoa hồng, event mở bán; đối chiếu giá với đối thủ.',
        indicators: [`Đã bán: ${sold}`, `Mục tiêu KH: ${unitsTarget}`],
      }),
    );
  } else if (
    totalUnits > 0 &&
    sold / totalUnits < 0.08 &&
    ['presale', 'selling', 'active'].includes(String(proj.status ?? ''))
  ) {
    risks.push(
      riskItem({
        code: 'sell_through_low',
        title: 'Tiến độ bán/tồn kho thấp',
        description: `Sell-through ${Math.round((sold / totalUnits) * 1000) / 10}% (${sold}/${totalUnits} căn).`,
        category: 'sales',
        probability_pct: 55,
        impact_pct: 70,
        recommendation:
          'Kích hoạt chiến dịch ưu đãi phân khu tồn cao; training đội sales theo segment.',
        indicators: [`Đã bán: ${sold}/${totalUnits}`],
      }),
    );
  }

  const trend = ((dash.monthly_trend as Array<Record<string, unknown>>) ?? []).filter(
    (t) => !['', '—'].includes(String(t.period_month ?? '')),
  );
  if (trend.length >= 2) {
    const lastTwo = trend.slice(-2);
    if (lastTwo.every((t) => Number(t.net_vnd ?? 0) < 0)) {
      risks.push(
        riskItem({
          code: 'cash_trend_declining',
          title: 'Xu hướng dòng tiền âm liên tiếp',
          description: '2 tháng gần nhất dòng tiền ròng âm — xu hướng xấu.',
          probability_pct: 72,
          impact_pct: 68,
          recommendation:
            'Họp cash committee tuần; ưu tiên thu nợ/cọc; cắt chi OPEX không thiết yếu.',
          indicators: lastTwo.map(
            (t) => `${t.period_month}: ${Number(t.net_vnd ?? 0).toLocaleString('en-US')}`,
          ),
        }),
      );
    }
  }

  const runway = forecast.runway_months as number | null | undefined;
  if (runway != null && runway < 3) {
    risks.push(
      riskItem({
        code: 'cash_runway_short',
        title: 'Runway dòng tiền ngắn',
        description: `Ước tính còn ~${runway} tháng trước khi cạn dòng tiền (theo burn rate hiện tại).`,
        probability_pct: runway === 0 ? 80 : 68,
        impact_pct: 92,
        recommendation:
          'Kế hoạch huy động vốn ngắn hạn; đàm phán lùi chi xây dựng/MKT; đẩy thu đợt 1 khách hàng.',
        indicators: [
          `Runway: ${runway} tháng`,
          `Burn TB: ${Number(forecast.avg_monthly_net_vnd ?? 0).toLocaleString('en-US')}/tháng`,
        ],
      }),
    );
  }

  risks.sort(
    (a, b) =>
      Number(b.score ?? 0) - Number(a.score ?? 0) || String(a.code ?? '').localeCompare(String(b.code ?? '')),
  );

  const levelCounts = { critical: 0, high: 0, medium: 0, low: 0 };
  for (const r of risks) {
    const lv = String(r.risk_level ?? 'medium');
    if (lv in levelCounts) levelCounts[lv as keyof typeof levelCounts] += 1;
  }
  const topScore = risks.length ? Number(risks[0].score ?? 0) : 0;
  let indexLabel: string;
  let riskIndex: string;
  if (levelCounts.critical >= 1 || topScore >= 50) {
    indexLabel = 'Rất cao';
    riskIndex = 'critical';
  } else if (levelCounts.high >= 2 || topScore >= 35) {
    indexLabel = 'Cao';
    riskIndex = 'high';
  } else if (risks.length) {
    indexLabel = 'Trung bình';
    riskIndex = 'medium';
  } else {
    indexLabel = 'Thấp';
    riskIndex = 'low';
  }

  return {
    risks,
    forecast,
    summary: {
      total: risks.length,
      critical: levelCounts.critical,
      high: levelCounts.high,
      medium: levelCounts.medium,
      low: levelCounts.low,
      risk_index: riskIndex,
      risk_index_label: indexLabel,
      top_score: topScore,
    },
  };
}

export function applyPredictedRisksToRegister(
  deps: AccountingDeps,
  projectId: number,
  opts: { codes?: string[]; ts?: string } = {},
): Record<string, number> {
  const tsVal = opts.ts ?? deps.accounting.nowTs();
  const pack = predictFinancialRisks(deps, projectId);
  const want = new Set((opts.codes ?? []).map((c) => String(c).trim()).filter(Boolean));
  const existing = new Set(
    deps.projects.listRisks(projectId).map((r) => String(r.title ?? '').trim()),
  );
  let applied = 0;
  let skipped = 0;

  for (const risk of (pack.risks as Array<Record<string, unknown>>) ?? []) {
    const code = String(risk.code ?? '');
    if (want.size && !want.has(code)) continue;
    const title = String(risk.title ?? '').trim();
    if (!title || existing.has(title)) {
      skipped += 1;
      continue;
    }
    let desc = String(risk.description ?? '');
    const marker = `[AI-KT:${code}]`;
    if (!desc.includes(marker)) desc = `${desc}\n${marker}`;
    deps.projects.saveRisk(
      projectId,
      {
        category: risk.category ?? 'finance',
        title,
        description: desc.slice(0, 4000),
        probability_pct: risk.probability_pct,
        impact_pct: risk.impact_pct,
        risk_level: risk.risk_level,
        mitigation: String(risk.recommendation ?? '').slice(0, 2000),
        status: 'open',
      },
      undefined,
      tsVal,
    );
    existing.add(title);
    applied += 1;
  }
  return { applied, skipped };
}

function projectExportBudgetRows(
  budget: Array<Record<string, unknown>>,
): [string[], unknown[][]] {
  const headers = ['Hạng mục', 'Loại', 'Kỳ', 'Kế hoạch (VND)', 'Thực tế (VND)', 'Chênh lệch (VND)', 'Ghi chú'];
  const rows = budget.map((b) => [
    b.line_item,
    b.category_label,
    b.period_month,
    b.planned_vnd,
    b.actual_vnd,
    b.variance_vnd,
    b.notes,
  ]);
  return [headers, rows];
}

function accountingExportCashFlowRows(
  lines: Array<Record<string, unknown>>,
): [string[], unknown[][]] {
  const headers = [
    'Mô tả',
    'Thu/Chi',
    'Hạng mục',
    'Kênh MKT',
    'Số tiền',
    'Kỳ',
    'Ngày GD',
    'Trạng thái',
    'Đối tác',
    'Nguồn',
    'Ghi chú',
  ];
  const rows = lines.map((c) => [
    c.line_item,
    c.flow_type_label,
    c.category_label,
    c.sub_category_label,
    c.amount_vnd,
    c.period_month,
    c.transaction_date,
    c.status_label,
    c.counterparty,
    c.source_type_label,
    c.notes,
  ]);
  return [headers, rows];
}

function accountingExportSummaryRows(
  proj: ReProjectRow,
  dash: Record<string, unknown>,
  forecast: Record<string, unknown>,
  riskPack: Record<string, unknown>,
): unknown[][] {
  const pnl = (dash.pnl as Record<string, unknown>) ?? {};
  const cf = (dash.cash_flow as Record<string, unknown>) ?? {};
  const mkt = (dash.marketing as Record<string, unknown>) ?? {};
  const sm = (riskPack.summary as Record<string, unknown>) ?? {};
  return [
    ['Dự án', proj.name],
    ['Mã', proj.code],
    ['DT kế hoạch (VND)', pnl.revenue_planned_vnd],
    ['DT thực tế (VND)', pnl.revenue_actual_vnd],
    ['Chi KH (VND)', pnl.cost_planned_vnd],
    ['Chi TT (VND)', pnl.cost_actual_vnd],
    ['LN kế hoạch (VND)', pnl.profit_planned_vnd],
    ['LN thực tế (VND)', pnl.profit_actual_vnd],
    ['Thu đã TT (VND)', cf.inflow_paid_vnd],
    ['Chi đã TT (VND)', cf.outflow_paid_vnd],
    ['Dòng tiền ròng TT (VND)', cf.net_cash_paid_vnd],
    ['MKT đã chi (VND)', mkt.cash_paid_vnd],
    ['MKT ROI (%)', mkt.roi_pct],
    ['Chỉ số rủi ro', sm.risk_index_label],
    ['Số rủi ro dự đoán', sm.total],
    ['Dự báo — outlook', forecast.outlook_label],
    ['Dự báo — LN 3 tháng (VND)', forecast.projected_profit_vnd],
    ['Dự báo — runway (tháng)', forecast.runway_months],
  ];
}

export function buildAccountingExportSheets(
  deps: AccountingDeps,
  projectId: number,
): Array<{ name: string; headers: string[]; rows: unknown[][] }> {
  const proj = deps.projects.fetchProject(projectId);
  if (!proj) throw new Error('Không tìm thấy dự án.');
  const dash = computeAccountingDashboard(deps, projectId);
  const forecast = forecastFinancialOutlook(deps, projectId, { dash });
  const riskPack = predictFinancialRisks(deps, projectId, { dash });
  const budget = deps.projects.listBudgetLines(projectId);
  const cash = listCashFlowLines(deps, projectId);
  const [budH, budR] = projectExportBudgetRows(budget);
  const [cfH, cfR] = accountingExportCashFlowRows(cash);
  const mkt = (dash.marketing as Record<string, unknown>) ?? {};
  const mktHeaders = ['Kênh', 'Dự kiến (VND)', 'Đã chi TT (VND)', 'Tổng ghi nhận (VND)'];
  const mktRows = ((mkt.by_channel as Array<Record<string, unknown>>) ?? []).map((c) => [
    c.sub_category_label,
    c.planned_vnd,
    c.paid_vnd,
    c.total_vnd,
  ]);
  const trHeaders = ['Kỳ', 'Thu (VND)', 'Chi (VND)', 'Ròng (VND)'];
  const trRows = ((dash.monthly_trend as Array<Record<string, unknown>>) ?? []).map((t) => [
    t.period_month,
    t.inflow_vnd,
    t.outflow_vnd,
    t.net_vnd,
  ]);
  const fcHeaders = ['Kỳ', 'Thu dự báo', 'Chi dự báo', 'Ròng dự báo'];
  const fcRows = ((forecast.projections as Array<Record<string, unknown>>) ?? []).map((p) => [
    p.period_month,
    p.projected_inflow_vnd,
    p.projected_outflow_vnd,
    p.projected_net_vnd,
  ]);
  const rkHeaders = [
    'Mã',
    'Tiêu đề',
    'Mô tả',
    'Loại',
    'Xác suất (%)',
    'Tác động (%)',
    'Mức',
    'Điểm',
    'Khuyến nghị',
    'Chỉ báo',
  ];
  const rkRows = ((riskPack.risks as Array<Record<string, unknown>>) ?? []).map((r) => [
    r.code,
    r.title,
    r.description,
    r.category_label,
    r.probability_pct,
    r.impact_pct,
    r.risk_level_label,
    r.score,
    r.recommendation,
    ((r.indicators as string[]) ?? []).join('; '),
  ]);
  const summary = accountingExportSummaryRows(proj, dash, forecast, riskPack);
  return [
    { name: 'Tổng quan KT', headers: ['Trường', 'Giá trị'], rows: summary },
    { name: 'P&L Ngân sách', headers: budH, rows: budR },
    { name: 'Dòng tiền', headers: cfH, rows: cfR },
    { name: 'Marketing', headers: mktHeaders, rows: mktRows },
    { name: 'Xu hướng', headers: trHeaders, rows: trRows },
    { name: 'Dự báo', headers: fcHeaders, rows: fcRows },
    { name: 'Rủi ro AI', headers: rkHeaders, rows: rkRows },
  ];
}

export function aiProjectFinanceQuery(
  _deps: AccountingDeps,
  _question: string,
  _opts: { reProjectId: number; createdBy?: string; ts?: string } = { reProjectId: 0 },
): Record<string, unknown> {
  const apiKey = String(process.env.ANTHROPIC_API_KEY ?? '').trim();
  if (!apiKey) {
    throw new ServiceUnavailableException({ error: 'ai_unavailable' });
  }
  throw new ServiceUnavailableException({ error: 'ai_unavailable' });
}
