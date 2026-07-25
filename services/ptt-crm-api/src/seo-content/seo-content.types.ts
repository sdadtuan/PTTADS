export interface SeoKeywordRow {
  id: number;
  customer_id: number;
  phrase: string;
  volume: number | null;
  difficulty: number | null;
  intent: string;
  business_value: string;
  cluster_id: number | null;
  opportunity_score: number | null;
  status: string;
  created_at: string | null;
  cluster_name?: string | null;
}

export interface SeoQuestionRow {
  id: number;
  customer_id: number;
  question_text: string;
  intent: string;
  funnel_stage: string;
  source: string;
  answer_score: number | null;
  status: string;
  brand_name: string;
  lifecycle_id: number | null;
  notes: string;
  created_at: string | null;
}

export interface SeoEntityGroupRow {
  entity_key: string;
  label: string;
  intent: string;
  keyword_count: number;
  avg_opportunity_score: number;
  top_opportunity_score: number;
  sample_keywords: Array<{ phrase: string; opportunity_score: number | null }>;
}

export interface SeoClusterRow {
  id: number;
  customer_id: number;
  name: string;
  intent: string;
  notes: string;
  status: string;
  keyword_count: number;
}

export interface SeoContentRow {
  id: number;
  customer_id: number;
  project_id: number | null;
  lifecycle_id: number | null;
  title: string;
  slug: string;
  content_type: string;
  workflow_status: string;
  target_keyword_id: number | null;
  target_question_id: number | null;
  intent: string;
  funnel_stage: string;
  owner_staff_id: number | null;
  due_date: string | null;
  publish_date: string | null;
  brief: Record<string, unknown>;
  outline: Record<string, unknown>;
  body_html: string;
  seo_score: number | null;
  aeo_score: number | null;
  created_at: string | null;
  updated_at: string | null;
  target_keyword?: SeoKeywordRow | null;
  target_question?: SeoQuestionRow | null;
  approvals?: SeoApprovalTimelineRow[];
}

export interface SeoApprovalTimelineRow {
  stage: string;
  status: string;
  notes: string;
  actor_id: string;
  created_at: string | null;
}

export interface SeoContentVersionRow {
  id: number;
  content_id: number;
  version_number: number;
  body_html?: string;
  changes_summary: string;
  created_by: string;
  created_at: string | null;
  body_length?: number;
}

export interface SeoPipelineBoard {
  columns: Array<{ key: string; label: string; items: SeoContentRow[] }>;
}

export interface SeoBriefPreviewResponse {
  title: string;
  brief: Record<string, unknown>;
  source: string;
  keyword_id?: number | null;
  question_id?: number | null;
  ai_available: boolean;
}

export interface SeoAeoChecklistResponse {
  content_id: number;
  items: Array<{ label: string; done: boolean }>;
  done_count: number;
  total: number;
  score_pct: number;
}

export interface SeoResearchConsoleResponse {
  keywords: SeoKeywordRow[];
  questions: SeoQuestionRow[];
  entities: SeoEntityGroupRow[];
  opportunities: SeoKeywordRow[];
  clusters: SeoClusterRow[];
}
