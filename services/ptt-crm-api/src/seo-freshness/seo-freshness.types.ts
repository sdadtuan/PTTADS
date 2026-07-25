export interface SeoFreshnessRow {
  id: number;
  customer_id: number;
  content_id: number;
  title: string;
  slug: string;
  workflow_status: string;
  decay_score: number;
  traffic_delta_pct: number | null;
  age_days: number;
  refresh_priority: string;
  last_scored_at: string | null;
  signals: Record<string, unknown>;
}
