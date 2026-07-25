export interface SeoAeoQueryRow {
  id: number;
  customer_id: number;
  query_text: string;
  brand_name: string;
  notes: string;
  lifecycle_id: number | null;
  created_at: string | null;
  last_scan_date: string | null;
  brand_visible: boolean;
  citation_status: string;
}

export interface SeoAeoMentionRow {
  id: number;
  question_id: number;
  ai_response: string;
  brand_visible: boolean;
  gap_notes: string;
  citation_status: string;
  created_at: string | null;
}

export interface SeoAeoCoverageSummary {
  customer_id: number;
  total: number;
  visible: number;
  coverage_pct: number;
}
