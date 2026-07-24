export interface CrossChannelChannelSummary {
  channel: string;
  spend: number;
  leads_crm: number;
  leads_platform: number;
  cpl: number | null;
  campaigns: number;
  unmapped_rows: number;
}

export interface CrossChannelSummaryResponse {
  ok: boolean;
  window_days: number;
  date_from: string;
  date_to: string;
  client_id: string | null;
  totals: {
    spend: number;
    leads_crm: number;
    cpl: number | null;
  };
  channels: CrossChannelChannelSummary[];
}
