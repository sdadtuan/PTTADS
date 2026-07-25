export interface SeoAuthoritySignalRow {
  id: number;
  customer_id: number;
  signal_type: string;
  source_domain: string;
  source_url: string;
  target_url: string;
  anchor_text: string;
  domain_rating: number | null;
  status: string;
  first_seen_at: string | null;
  last_seen_at: string | null;
  notes: string;
  created_at: string | null;
}

export interface SeoAuthoritySummary {
  backlinks_active: number;
  backlinks_lost: number;
  citations: number;
  brand_mentions: number;
  pr_signals: number;
  avg_dr: number;
  total_signals: number;
}
