export type ChannelReportKind = 'meta' | 'zalo';

export type ChannelReportScope = 'clients' | 'campaigns';

export type ChannelReportFormat = 'csv' | 'pdf';

export type ChannelReportCadence = 'weekly' | 'monthly';

export interface ChannelReportScheduleRow {
  id: string;
  client_id: string;
  client_name: string;
  report_scope: ChannelReportScope;
  export_format: ChannelReportFormat;
  window_days: number;
  cadence: ChannelReportCadence;
  day_of_week: number;
  day_of_month: number;
  recipient_emails: string[];
  cc_emails: string[];
  bcc_emails: string[];
  portal_link_enabled: boolean;
  active: boolean;
  next_run_at: string | null;
  last_sent_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChannelReportScheduleListResponse {
  ok: boolean;
  items: ChannelReportScheduleRow[];
  total: number;
  limit: number;
  offset: number;
  table_ready: boolean;
}

export interface CreateChannelReportScheduleBody {
  client_id: string;
  report_scope?: ChannelReportScope;
  export_format?: ChannelReportFormat;
  window_days?: number;
  cadence?: ChannelReportCadence;
  day_of_week?: number;
  day_of_month?: number;
  recipient_emails?: string[];
  cc_emails?: string[];
  bcc_emails?: string[];
  portal_link_enabled?: boolean;
}

export interface PatchChannelReportScheduleBody {
  report_scope?: ChannelReportScope;
  export_format?: ChannelReportFormat;
  window_days?: number;
  cadence?: ChannelReportCadence;
  day_of_week?: number;
  day_of_month?: number;
  recipient_emails?: string[];
  cc_emails?: string[];
  bcc_emails?: string[];
  portal_link_enabled?: boolean;
  active?: boolean;
}
