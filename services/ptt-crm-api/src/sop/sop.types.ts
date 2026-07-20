export interface SopTemplateRow {
  id: number;
  code: string;
  name: string;
  channel: string;
  description: string;
  notes: string;
  active: number;
  created_at: string;
  updated_at: string;
}

export interface SopStepRow {
  id: number;
  template_id: number;
  position: number;
  title: string;
  description: string;
  offset_days: number;
  duration_days: number;
  role: string;
  required: number;
  checklist_json: string;
  created_at: string;
  updated_at: string;
}

export interface SopRunRow {
  id: number;
  campaign_id: number | null;
  template_id: number | null;
  name: string;
  status: string;
  start_date: string;
  notes: string;
  created_at: string;
  updated_at: string;
  template_name?: string;
  template_channel?: string;
  campaign_name?: string;
  campaign_code?: string;
  stats?: SopRunStats;
}

export interface SopRunStats {
  total: number;
  done: number;
  skipped: number;
  in_progress: number;
  todo: number;
  overdue: number;
}

export interface CreateSopRunBody {
  name: string;
  template_id?: number | null;
  campaign_id?: number | null;
  start_date?: string;
  status?: string;
  notes?: string;
  generate_tasks?: boolean;
}

export const CRM_SOP_RUN_STATUSES = ['draft', 'active', 'paused', 'completed', 'archived'] as const;

export function normalizeSopRunStatus(raw?: string): string {
  const code = String(raw ?? 'active').trim().toLowerCase();
  return (CRM_SOP_RUN_STATUSES as readonly string[]).includes(code) ? code : 'active';
}

export function isValidDateYmd(raw: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(String(raw ?? '').trim());
}

export function addDaysIso(startDate: string, days: number): string {
  const d = new Date(`${startDate}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return '';
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}
