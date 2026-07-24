export type MetaOpsWebhookEventType = 'meta_account_disabled' | 'ad_disapproved';

export interface MetaOpsWebhookEvent {
  event_type: MetaOpsWebhookEventType;
  external_account_id: string | null;
  external_ad_id: string | null;
  external_campaign_id: string | null;
  account_status?: string;
  disable_reason?: string | null;
  effective_status?: string;
  field: string;
}

export interface MetaOpsWebhookProcessResult {
  ok: boolean;
  skipped?: boolean;
  reason?: string;
  events: number;
  created: number;
  results: Array<Record<string, unknown>>;
}
