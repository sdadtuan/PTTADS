export interface SeoRankKeywordRow {
  id: number;
  customer_id: number;
  keyword_id: number | null;
  phrase: string;
  target_url: string;
  locale: string;
  status: string;
  latest_position: number | null;
  latest_date: string | null;
  created_at: string | null;
}

export interface SeoRankSovSummary {
  customer_id: number;
  domain_hint: string;
  tracked: number;
  in_top_n: number;
  sov_pct: number;
  top_n: number;
}

export interface SeoRankCaptureResult {
  customer_id: number;
  captured: number;
  domain_hint: string;
  errors: string[];
}
