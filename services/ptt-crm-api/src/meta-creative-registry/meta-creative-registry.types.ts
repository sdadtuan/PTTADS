export type MetaCreativeLinkSource = 'manual' | 'campaign_write' | 'graph_sync';

export interface MetaAdCreativeLinkRow {
  id: string;
  client_id: string;
  creative_submission_id: string;
  external_ad_id: string;
  external_adset_id: string | null;
  external_campaign_id: string | null;
  external_creative_id: string | null;
  link_source: MetaCreativeLinkSource | string;
  is_active: boolean;
  linked_by: string | null;
  note: string | null;
  creative_title: string | null;
  creative_status: string | null;
  creative_asset_url: string | null;
  creative_version: number | null;
  created_at: string;
  updated_at: string;
}

export interface MetaCreativeLinksListResponse {
  ok: boolean;
  disabled?: boolean;
  reason?: string;
  hint?: string;
  rows: MetaAdCreativeLinkRow[];
  count: number;
}

export interface MetaCreativeLinkResolveResponse {
  ok: boolean;
  disabled?: boolean;
  reason?: string;
  hint?: string;
  found: boolean;
  client_id: string;
  external_ad_id: string;
  link: MetaAdCreativeLinkRow | null;
}

export interface MetaCreativeLinkMutationResponse {
  ok: boolean;
  disabled?: boolean;
  error?: string;
  errors?: string[];
  replaced?: boolean;
  link?: MetaAdCreativeLinkRow;
}
