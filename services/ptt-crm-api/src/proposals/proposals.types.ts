export interface ProposalRow {
  id: number;
  customer_id: number;
  lifecycle_id: number | null;
  service_slugs: string[];
  total_vnd: number;
  timeline_months: number;
  notes: string;
  ai_output: Record<string, unknown>;
  generated?: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateProposalBody {
  customer_id: number;
  service_slugs: string[];
  total_vnd?: number;
  timeline_months?: number;
  notes?: string;
  lifecycle_id?: number | null;
}
