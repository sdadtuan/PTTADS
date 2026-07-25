export type PortalNotificationCategory =
  | 'creative_pending'
  | 'email_pending'
  | 'seo_pending'
  | 'campaign_milestone'
  | 'system';

export interface PortalNotificationRow {
  id: string;
  client_id: string;
  portal_user_id: string | null;
  category: PortalNotificationCategory | string;
  title: string;
  body: string | null;
  link_url: string | null;
  meta: Record<string, unknown>;
  read: boolean;
  read_at: string | null;
  created_at: string;
}

export interface PortalNotificationListResponse {
  ok: boolean;
  client_id: string;
  count: number;
  unread: number;
  rows: PortalNotificationRow[];
  table_ready: boolean;
}

export interface PortalNotificationSummaryResponse {
  ok: boolean;
  client_id: string;
  unread: number;
  pending_creatives: number;
  pending_email: number;
  pending_seo: number;
  table_ready: boolean;
}

export interface EmitPortalNotificationInput {
  clientId: string;
  category: PortalNotificationCategory | string;
  title: string;
  body?: string | null;
  linkUrl?: string | null;
  meta?: Record<string, unknown>;
  portalUserId?: string | null;
  approverOnly?: boolean;
}

export interface PortalNotifyWebhookResult {
  ok: boolean;
  skipped?: boolean;
  error?: string;
}
