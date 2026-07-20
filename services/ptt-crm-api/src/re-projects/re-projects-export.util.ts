import { ReProjectRow } from './re-projects.types';

export interface ExportSheet {
  name: string;
  headers: string[];
  rows: unknown[][];
}

export interface ExportJsonBundle {
  filename: string;
  format: 'json';
  report: string;
  sheets: ExportSheet[];
}

function exportJoin(val: unknown): string {
  if (Array.isArray(val)) {
    return val
      .map((x) => String(x).trim())
      .filter(Boolean)
      .join('; ');
  }
  if (val && typeof val === 'object') {
    return JSON.stringify(val);
  }
  return String(val ?? '');
}

export function projectExportSummaryRows(
  proj: ReProjectRow,
  summary: Record<string, unknown>,
  workflow: Record<string, unknown>,
): unknown[][] {
  return [
    ['Mã dự án', proj.code],
    ['Tên dự án', proj.name],
    ['Loại hình', proj.project_type_label],
    ['Trạng thái', proj.status_label],
    ['Địa chỉ', proj.location_address],
    ['Quận/Huyện', proj.district],
    ['Tỉnh/TP', proj.city],
    ['Chủ đầu tư', proj.developer_name],
    ['Tổng căn', proj.total_units],
    ['Đã bán', proj.sold_units],
    ['Tiến độ bán (%)', proj.sell_through_pct],
    ['Doanh thu mục tiêu (VND)', proj.revenue_target_vnd],
    ['Căn còn hàng', summary.products_available],
    ['Căn đã bán (tồn kho)', summary.products_sold],
    ['Số KPI', summary.kpi_count],
    ['KPI đạt TB (%)', summary.kpi_avg_achievement_pct],
    ['Số rủi ro', summary.risk_count],
    ['Rủi ro cao', summary.high_risk_count],
    ['DT kế hoạch (VND)', summary.budget_revenue_planned_vnd],
    ['DT thực tế (VND)', summary.budget_revenue_actual_vnd],
    ['Chi phí KH (VND)', summary.budget_cost_planned_vnd],
    ['Chi phí TT (VND)', summary.budget_cost_actual_vnd],
    ['LNTT kế hoạch (VND)', summary.profit_planned_vnd],
    ['LNTT thực tế (VND)', summary.profit_actual_vnd],
    ['Tiến độ quy trình (%)', workflow.progress_pct],
    ['Bước tiếp theo', workflow.next_step_id],
  ];
}

export function projectExportWorkflowRows(
  workflow: Record<string, unknown>,
): [string[], unknown[][]] {
  const headers = ['STT', 'Bước', 'Mô tả', 'Trạng thái'];
  const steps = (workflow.steps as Array<Record<string, unknown>>) ?? [];
  const rows = steps.map((s) => [s.order, s.label, s.hint, s.status_label]);
  return [headers, rows];
}

export function projectExportKpiRows(
  kpis: Array<Record<string, unknown>>,
): [string[], unknown[][]] {
  const headers = [
    'Chỉ tiêu',
    'Mã',
    'Loại',
    'Kỳ',
    'Mục tiêu',
    'Thực tế',
    'Đạt (%)',
    'Trọng số',
    'Nhân viên',
    'Phòng ban',
    'Trạng thái',
    'Ghi chú',
  ];
  const rows = kpis.map((k) => [
    k.metric_name,
    k.metric_code,
    k.category_label,
    k.period_month,
    k.target_value,
    k.actual_value,
    k.achievement_pct,
    k.weight_pct,
    k.owner_display ?? k.owner_name,
    k.owner_department,
    k.track_status_label ?? k.track_status,
    k.notes,
  ]);
  return [headers, rows];
}

export function projectExportProductRows(
  products: Array<Record<string, unknown>>,
): [string[], unknown[][]] {
  const headers = [
    'Mã căn',
    'Phân khu',
    'Block',
    'Tầng',
    'Dòng SP',
    'Typology',
    'Loại chi tiết',
    'DT (m²)',
    'PN',
    'Căn góc',
    'Giá niêm yết',
    'Trạng thái',
    'NV phụ trách',
    'Ghi chú',
  ];
  const rows = products.map((p) => [
    p.unit_code,
    p.zone,
    p.tower,
    p.floor,
    p.product_line_label ?? p.product_line,
    p.typology_label ?? p.typology,
    p.product_type,
    p.area_m2,
    p.bedrooms,
    p.is_corner ? 'Có' : '',
    p.list_price_vnd,
    p.status_label,
    p.sales_staff_name,
    p.notes,
  ]);
  return [headers, rows];
}

export function projectExportRiskRows(
  risks: Array<Record<string, unknown>>,
): [string[], unknown[][]] {
  const headers = [
    'Rủi ro',
    'Loại',
    'Mức',
    'Xác suất',
    'Tác động',
    'Điểm',
    'Biện pháp',
    'Owner',
    'Trạng thái',
  ];
  const rows = risks.map((r) => [
    r.title,
    r.category_label,
    r.risk_level_label,
    r.probability_pct,
    r.impact_pct,
    r.score,
    r.mitigation,
    r.owner_name,
    r.status,
  ]);
  return [headers, rows];
}

export function projectExportBudgetRows(
  budget: Array<Record<string, unknown>>,
): [string[], unknown[][]] {
  const headers = [
    'Hạng mục',
    'Loại',
    'Kỳ',
    'Kế hoạch (VND)',
    'Thực tế (VND)',
    'Chênh lệch (VND)',
    'Ghi chú',
  ];
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

export function projectExportPlanRows(proj: ReProjectRow): [string[], unknown[][]] {
  const bp = (proj.business_plan ?? {}) as Record<string, unknown>;
  const mp = (proj.marketing_plan ?? {}) as Record<string, unknown>;
  const sp = (proj.sales_plan ?? {}) as Record<string, unknown>;
  const sw = (bp.swot ?? {}) as Record<string, unknown>;
  const headers = ['Hạng mục', 'Trường', 'Giá trị'];
  const rows: unknown[][] = [
    ['Kế hoạch KD', 'Tầm nhìn', bp.vision],
    ['Kế hoạch KD', 'Sứ mệnh', bp.mission],
    ['Kế hoạch KD', 'Thị trường mục tiêu', bp.target_market],
    ['Kế hoạch KD', 'Doanh thu mục tiêu', bp.revenue_target_vnd],
    ['Kế hoạch KD', 'Điểm mạnh', exportJoin(sw.strengths)],
    ['Kế hoạch KD', 'Điểm yếu', exportJoin(sw.weaknesses)],
    ['Kế hoạch KD', 'Trạng thái duyệt', bp.approval_status],
    ['Marketing', 'Định vị', mp.positioning],
    ['Marketing', 'Lead/tháng', mp.lead_target_monthly],
    ['Marketing', 'Ngân sách', mp.budget_total_vnd],
    ['Marketing', 'Mục tiêu', exportJoin(mp.objectives)],
    ['Marketing', 'Kênh', exportJoin(mp.channels)],
    ['Marketing', 'Trạng thái duyệt', mp.approval_status],
    ['Bán hàng', 'Doanh thu mục tiêu', sp.revenue_target_vnd],
    ['Bán hàng', 'Số căn mục tiêu', sp.units_target],
    ['Bán hàng', 'Chiến lược giá', sp.pricing_strategy],
    ['Bán hàng', 'Trạng thái duyệt', sp.approval_status],
  ];
  return [headers, rows];
}

export type ExportReportType =
  | 'full'
  | 'summary'
  | 'workflow'
  | 'kpis'
  | 'products'
  | 'risks'
  | 'budget'
  | 'plans';

export function buildExportFilename(projectCode: string, projectId: number, report: string): string {
  const code = String(projectCode || `du-an-${projectId}`).trim() || `du-an-${projectId}`;
  const stamp = new Date().toISOString().slice(0, 10);
  const base = `re-${code}-${stamp}`.replace(/\s+/g, '-');
  const suffix: Record<string, string> = {
    summary: 'tom-tat',
    workflow: 'quy-trinh',
    kpis: 'kpi',
    products: 'ton-kho',
    risks: 'rui-ro',
    budget: 'ngan-sach',
    plans: 'ke-hoach',
    full: 'tong-hop',
  };
  return `${base}-${suffix[report] ?? report}.json`;
}

export function buildExportJsonBundle(
  report: ExportReportType,
  pack: {
    project: ReProjectRow;
    summary: Record<string, unknown>;
    workflow: Record<string, unknown>;
    kpis: Array<Record<string, unknown>>;
    products: Array<Record<string, unknown>>;
    risks: Array<Record<string, unknown>>;
    budget: Array<Record<string, unknown>>;
  },
): ExportJsonBundle {
  const proj = pack.project;
  const filename = buildExportFilename(proj.code, proj.id, report);
  const sheets: ExportSheet[] = [];

  if (report === 'summary' || report === 'full') {
    sheets.push({
      name: 'Tóm tắt',
      headers: ['Trường', 'Giá trị'],
      rows: projectExportSummaryRows(proj, pack.summary, pack.workflow),
    });
  }
  if (report === 'workflow' || report === 'full') {
    const [headers, rows] = projectExportWorkflowRows(pack.workflow);
    sheets.push({ name: 'Quy trình', headers, rows });
  }
  if (report === 'plans' || report === 'full') {
    const [headers, rows] = projectExportPlanRows(proj);
    sheets.push({ name: 'Kế hoạch', headers, rows });
  }
  if (report === 'kpis' || report === 'full') {
    const [headers, rows] = projectExportKpiRows(pack.kpis);
    sheets.push({ name: 'KPI', headers, rows });
  }
  if (report === 'products' || report === 'full') {
    const [headers, rows] = projectExportProductRows(pack.products);
    sheets.push({ name: 'Tồn kho', headers, rows });
  }
  if (report === 'risks' || report === 'full') {
    const [headers, rows] = projectExportRiskRows(pack.risks);
    sheets.push({ name: 'Rủi ro', headers, rows });
  }
  if (report === 'budget' || report === 'full') {
    const [headers, rows] = projectExportBudgetRows(pack.budget);
    sheets.push({ name: 'Ngân sách', headers, rows });
  }

  return { filename, format: 'json', report, sheets };
}
