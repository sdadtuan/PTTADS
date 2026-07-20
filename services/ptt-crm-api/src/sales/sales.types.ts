export interface SalesPlanRow {
  id: number;
  title: string;
  fiscal_year: number;
  period_start: string;
  period_end: string;
  revenue_target_vnd: number;
  status: string;
  status_label: string;
  summary: string;
  strategy_notes: string;
  created_at: string;
  updated_at: string;
  targets_sum?: number;
  actuals_sum?: number;
  revenue_progress_pct?: number | null;
}

export interface CreateSalesPlanBody {
  title: string;
  fiscal_year?: number;
  period_start?: string;
  period_end?: string;
  revenue_target_vnd?: number;
  status?: string;
  summary?: string;
  strategy_notes?: string;
}

export interface FunnelStageStat {
  stage: string;
  label: string;
  count: number;
  avg_hours: number;
  sla_hours: number;
  conversion_from_prev_pct: number | null;
  owner_role: string;
}

export interface FunnelStats {
  generated_at: string;
  totals: {
    cases: number;
    open_pipeline: number;
    unassigned: number;
    sla_overdue: number;
    won: number;
    lost: number;
    win_rate_pct: number | null;
    pipeline_value_vnd: number;
  };
  stages: FunnelStageStat[];
  by_staff: Record<string, { open: number; won: number; lost: number; overdue: number }>;
  by_channel: Record<string, number>;
  bottlenecks: Array<{
    stage: string;
    label: string;
    count: number;
    avg_hours: number;
    sla_hours: number;
    severity: string;
  }>;
}

export interface SalesSummaryResponse {
  funnel: FunnelStats;
  active_plan: SalesPlanRow | null;
  counts: {
    partners_active: number;
    transactions_open: number;
    trainings_upcoming: number;
    market_reports: number;
    kd_staff: number;
  };
  pipeline_labels: Record<string, string>;
  pipeline_stages: string[];
}

export interface SalesPartnerRow {
  id: number;
  partner_type: string;
  partner_type_label: string;
  name: string;
  phone: string;
  email: string;
  company: string;
  territory: string;
  commission_pct: number | null;
  status: string;
  status_label: string;
  assigned_staff_id: number | null;
  assigned_staff_name: string;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface CreatePartnerBody {
  name: string;
  partner_type?: string;
  phone?: string;
  email?: string;
  company?: string;
  territory?: string;
  commission_pct?: number | null;
  status?: string;
  assigned_staff_id?: number | null;
  notes?: string;
}

export interface SalesTrainingRow {
  id: number;
  title: string;
  training_date: string;
  trainer_name: string;
  topic: string;
  content_summary: string;
  materials_url: string;
  attendee_staff_ids_list: number[];
  status: string;
  status_label: string;
  created_at: string;
  updated_at: string;
}

export interface CreateTrainingBody {
  title: string;
  training_date?: string;
  trainer_name?: string;
  topic?: string;
  content_summary?: string;
  materials_url?: string;
  status?: string;
}

export interface SalesMarketRow {
  id: number;
  title: string;
  research_date: string;
  area: string;
  property_type: string;
  competitor_notes: string;
  price_analysis: string;
  strategy_proposal: string;
  status: string;
  status_label: string;
  created_at: string;
  updated_at: string;
}

export interface CreateMarketBody {
  title: string;
  research_date?: string;
  area?: string;
  property_type?: string;
  competitor_notes?: string;
  price_analysis?: string;
  strategy_proposal?: string;
  status?: string;
}

export interface SalesTransactionRow {
  id: number;
  case_id: number | null;
  contract_id: number | null;
  customer_id: number | null;
  customer_name: string;
  transaction_type: string;
  transaction_type_label: string;
  property_ref: string;
  stage: string;
  stage_label: string;
  deal_value_vnd: number;
  assigned_staff_id: number | null;
  assigned_staff_name: string;
  case_title: string;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface PipelineCaseRow {
  id: number;
  title: string;
  pipeline_stage: string;
  pipeline_stage_label: string;
  is_terminal: boolean;
  deal_value_vnd: number;
  status: string;
  assigned_staff_id: number | null;
  customer_id: number | null;
  customer_name: string;
  staff_name: string;
  created_at: string;
  stage_entered_at: string;
}

export interface SalesReportResponse {
  funnel_totals: FunnelStats['totals'];
  staff_performance: Array<{ name: string; open: number; won: number; lost: number; overdue: number }>;
  revenue_closed_cases: number;
  revenue_closed_tx: number;
  targets: Array<Record<string, unknown>>;
  bottlenecks: FunnelStats['bottlenecks'];
}

export const SALES_PLAN_STATUSES = ['draft', 'active', 'closed'] as const;

export const SALES_PLAN_STATUS_LABELS: Record<string, string> = {
  draft: 'Nháp',
  active: 'Đang triển khai',
  closed: 'Đã đóng',
};

export function normalizeSalesPlanStatus(raw?: string): string {
  const code = String(raw ?? '').trim().toLowerCase();
  return (SALES_PLAN_STATUSES as readonly string[]).includes(code) ? code : 'draft';
}
