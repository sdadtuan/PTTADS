export interface MarketingPlanRow {
  id: number;
  code: string;
  name: string;
  status: string;
  status_label: string;
  priority: string;
  priority_label: string;
  fiscal_year: number;
  period_label: string;
  north_star: string;
  objectives: string;
  pillars_json: string;
  audiences: string;
  channels_focus_json: string;
  budget_planned_vnd: number;
  budget_actual_vnd: number;
  success_metrics_json: string;
  risks_notes: string;
  owner_staff_id: number | null;
  owner_name: string;
  start_date: string;
  end_date: string;
  notes: string;
  strategy_framework_json: string;
  target_market_prof_json: string;
  target_market_steps4_json: string;
  khtn_market_research_json: string;
  created_at: string;
  updated_at: string;
  linked_campaign_count?: number;
  milestone_total?: number;
  milestone_done?: number;
}

export interface MarketingPlanMilestoneRow {
  id: number;
  plan_id: number;
  position: number;
  title: string;
  description: string;
  due_date: string;
  status: string;
  owner_staff_id: number | null;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface MarketingPlanCampaignRow {
  id: number;
  name: string;
  code: string;
  status: string;
  channel: string;
  [key: string]: unknown;
}

export interface CreateMarketingPlanBody {
  name: string;
  code?: string;
  status?: string;
  priority?: string;
  fiscal_year?: number;
  period_label?: string;
  north_star?: string;
  objectives?: string;
  audiences?: string;
  risks_notes?: string;
  notes?: string;
  owner_staff_id?: number | null;
  start_date?: string;
  end_date?: string;
  budget_planned_vnd?: number;
  budget_actual_vnd?: number;
}

export interface PatchMarketingPlanBody {
  name?: string;
  status?: string;
  priority?: string;
  notes?: string;
  objectives?: string;
}

export const CRM_MARKETING_PLAN_STATUSES = [
  'draft',
  'review',
  'active',
  'paused',
  'completed',
  'archived',
  'cancelled',
] as const;

export const CRM_MARKETING_PLAN_STATUS_LABELS: Record<string, string> = {
  draft: 'Nháp',
  review: 'Chờ phê duyệt',
  active: 'Đang triển khai',
  paused: 'Tạm dừng',
  completed: 'Đã đóng chu kỳ',
  archived: 'Lưu trữ',
  cancelled: 'Huỷ bỏ',
};

export const CRM_MARKETING_PLAN_PRIORITIES = ['low', 'normal', 'high', 'critical'] as const;

export const CRM_MARKETING_PLAN_PRIORITY_LABELS: Record<string, string> = {
  low: 'Thấp',
  normal: 'Bình thường',
  high: 'Cao',
  critical: 'Rất cao',
};

export function normalizeMarketingPlanStatus(raw?: string): string {
  const code = String(raw ?? '').trim().toLowerCase();
  return (CRM_MARKETING_PLAN_STATUSES as readonly string[]).includes(code) ? code : 'draft';
}

export function normalizeMarketingPlanPriority(raw?: string): string {
  const code = String(raw ?? '').trim().toLowerCase();
  return (CRM_MARKETING_PLAN_PRIORITIES as readonly string[]).includes(code) ? code : 'normal';
}
