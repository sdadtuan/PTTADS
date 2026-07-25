export type OnboardOrchestratorModule = 'crm' | 'agency' | 'meta' | 'zalo' | 'seo' | 'email' | 'portal';

export type OnboardOrchestratorStepStatus = 'pending' | 'done' | 'skipped' | 'optional';

export interface OnboardOrchestratorStep {
  key: string;
  label: string;
  module: OnboardOrchestratorModule;
  sort_order: number;
  status: OnboardOrchestratorStepStatus;
  href: string | null;
  auto_detected: boolean;
  manual_only: boolean;
  optional: boolean;
  checklist_item_key: string | null;
  hint: string | null;
  detection_detail: string | null;
}

export interface OnboardOrchestratorProgress {
  total: number;
  completed: number;
  percent: number;
  required_total: number;
  required_completed: number;
  required_percent: number;
}

export interface OnboardOrchestratorResponse {
  client_id: string;
  client_code: string;
  client_name: string;
  client_status: string;
  steps: OnboardOrchestratorStep[];
  progress: OnboardOrchestratorProgress;
  checklist_progress: OnboardOrchestratorProgress;
  linked_lifecycle_url: string | null;
  synced_at: string | null;
}

export interface OnboardOrchestratorSyncResponse {
  client_id: string;
  synced_items: string[];
  orchestrator: OnboardOrchestratorResponse;
  lifecycle_auto_advance?: {
    eligible: boolean;
    lifecycle_id: number | null;
    advanced: boolean;
    reason: string;
  };
}

export interface OnboardOrchestratorSignals {
  linkedLifecycles: Array<{ lifecycle_id: number; stage: string; service_delivery_url: string }>;
  checklistItems: Array<{ item_key: string; label: string; completed: boolean }>;
  checklistProgress: OnboardOrchestratorProgress;
  clientStatus: string;
  metaAccounts: Array<{ has_token: boolean; token_status: string | null; pixel_id: string | null }>;
  zaloAccounts: Array<{ has_token: boolean; token_status: string | null; form_ids: string[] }>;
  zaloLeadCount: number;
  zaloFormConfigured: boolean;
  zaloSyncOk: boolean;
  portalUsers: Array<{ role: string; active: boolean }>;
  seo: { mapped: boolean; customer_id: number | null; gsc_connected: boolean; has_settings: boolean };
  email: { workspace: boolean; verified_domain: boolean };
  leadCount: number;
}

export interface OnboardOrchestratorStepDef {
  key: string;
  label: string;
  module: OnboardOrchestratorModule;
  sort_order: number;
  optional?: boolean;
  manual_only?: boolean;
  checklist_item_key?: string;
  href?: (ctx: { clientId: string; seoCustomerId: number | null; lifecycleUrl: string | null }) => string | null;
  detect: (signals: OnboardOrchestratorSignals) => { done: boolean; detail: string | null };
}
