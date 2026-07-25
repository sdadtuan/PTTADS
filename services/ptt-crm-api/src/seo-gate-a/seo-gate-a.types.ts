export interface SeoGateAFlagState {
  PTT_SEO_GOVERNANCE_ENABLED: boolean;
  PTT_PORTAL_SEO_ENABLED: boolean;
  PTT_SEO_EXPERIMENTS_ENABLED: boolean;
}

export interface SeoGateASoakSummary {
  ok: boolean;
  skipped?: boolean;
  required_days: number;
  sample_count: number;
  span_days: number | null;
  failure_count: number;
  log_path: string;
}

export interface SeoGateAStagedStep {
  id: string;
  label: string;
  enabled: boolean;
  env_keys: string[];
}

export interface SeoGateAReadinessResponse {
  ok: boolean;
  phase: '7';
  gate: 'A';
  generated_at: string;
  flags: SeoGateAFlagState;
  staged_steps: SeoGateAStagedStep[];
  ops_web_routes: string[];
  soak: SeoGateASoakSummary;
  artifacts: Record<string, string>;
  qa_checklist: Array<{ id: string; label: string; status: 'open' | 'automated' | 'manual' }>;
  nginx_redirect: string;
  notes: string[];
}

export interface SeoGateASignoffTemplate {
  phase: string;
  component: string;
  environment: string;
  flags_applied: SeoGateAFlagState;
  staged_steps: Record<string, boolean>;
  gates: Record<string, boolean | number | null>;
  signoffs: Record<string, string | null>;
}
