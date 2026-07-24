export const COMPLIANCE_EXPORT_VERSION = '1.0';

export interface MetaComplianceExportResponse {
  ok: boolean;
  export_version: string;
  generated_at: string;
  client_id: string;
  client: Record<string, unknown> | null;
  channel_accounts: Array<Record<string, unknown>>;
  performance_summary: Record<string, unknown>;
  open_alerts: Array<Record<string, unknown>>;
  recent_campaign_writes: Array<Record<string, unknown>>;
  tracking_summary: Record<string, unknown>;
  redaction: {
    tokens_redacted: boolean;
    pii_redacted: boolean;
    note: string;
  };
}
