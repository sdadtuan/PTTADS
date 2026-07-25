export interface EmailGateAFlagState {
  PTT_EMAIL_ENABLED: boolean;
  PTT_EMAIL_SEND_ENABLED: boolean;
  PTT_EMAIL_JOURNEYS_ENABLED: boolean;
  PTT_EMAIL_PORTAL_ENABLED: boolean;
}

export interface EmailGateASoakSummary {
  ok: boolean;
  skipped?: boolean;
  required_days: number;
  sample_count: number;
  span_days: number | null;
  failure_count: number;
  log_path: string;
}

export interface EmailGateAStagedStep {
  id: string;
  label: string;
  enabled: boolean;
  env_keys: string[];
}

export interface EmailGateAReadinessResponse {
  ok: boolean;
  phase: string;
  gate: string;
  generated_at: string;
  flags: EmailGateAFlagState;
  staged_steps: EmailGateAStagedStep[];
  ops_web_routes: string[];
  soak: EmailGateASoakSummary;
  artifacts: Record<string, string>;
  qa_checklist: Array<{ id: string; label: string; status: string }>;
  nginx_redirect?: string;
  notes: string[];
}

export interface EmailGateASignoffTemplate {
  phase: string;
  component: string;
  flags_applied: EmailGateAFlagState;
}
