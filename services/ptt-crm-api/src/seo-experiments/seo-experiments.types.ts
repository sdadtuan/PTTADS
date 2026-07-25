export interface SeoExperimentRow {
  id: number;
  customer_id: number;
  title: string;
  hypothesis: string;
  experiment_type: string;
  target_url: string;
  content_id: number | null;
  status: string;
  started_at: string | null;
  ended_at: string | null;
  owner_id: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface SeoExperimentObservationRow {
  id: number;
  experiment_id: number;
  variant_key: string;
  metric_date: string;
  metric_name: string;
  metric_value: number;
  source: string;
}
