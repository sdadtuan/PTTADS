import { normalizeCreativeChannel } from '../creatives/creative-channel.util';
import { readFormIdsFromMeta } from '../agency/channel-meta.util';

export const ZALO_LAUNCH_QA_CHECKLIST_ITEMS: Record<
  string,
  { label: string; completed: boolean; completed_by?: string; note?: string }
> = {
  zalo_oauth_token: { label: 'Zalo OAuth token valid', completed: false },
  zalo_form_ids_configured: { label: 'Lead form IDs configured', completed: false },
};

export const ZALO_LAUNCH_QA_ITEM_KEYS = Object.keys(ZALO_LAUNCH_QA_CHECKLIST_ITEMS);

export function isZaloLaunchQaEnabled(): boolean {
  return ['1', 'true', 'yes', 'on'].includes(
    (process.env.PTT_ZALO_ADS_PILOT ?? process.env.PTT_ZALO_INSIGHTS_SYNC ?? '0')
      .trim()
      .toLowerCase(),
  );
}

export function isZaloLaunchQaItemKey(itemKey: string): boolean {
  return ZALO_LAUNCH_QA_ITEM_KEYS.includes(itemKey.trim());
}

export function mergeZaloLaunchQaChecklist<T extends Record<string, unknown>>(
  checklist: T,
  hasZaloChannel: boolean,
): T & typeof ZALO_LAUNCH_QA_CHECKLIST_ITEMS {
  if (!isZaloLaunchQaEnabled() || !hasZaloChannel) {
    return checklist as T & typeof ZALO_LAUNCH_QA_CHECKLIST_ITEMS;
  }
  const merged = { ...checklist } as T & typeof ZALO_LAUNCH_QA_CHECKLIST_ITEMS;
  for (const [key, template] of Object.entries(ZALO_LAUNCH_QA_CHECKLIST_ITEMS)) {
    if (!(key in merged)) {
      merged[key as keyof typeof merged] = { ...template } as (typeof merged)[keyof typeof merged];
    }
  }
  return merged;
}

export interface ZaloLaunchQaEvalItem {
  key: string;
  passed: boolean;
  note: string;
}

export interface ZaloChannelAccountRow {
  has_account: boolean;
  has_token: boolean;
  form_ids: string[];
}

export function evaluateZaloLaunchQaItems(account: ZaloChannelAccountRow | null): ZaloLaunchQaEvalItem[] {
  const hasAccount = Boolean(account?.has_account);
  const hasToken = Boolean(account?.has_token);
  const formIds = account?.form_ids ?? [];

  return [
    {
      key: 'zalo_oauth_token',
      passed: hasAccount && hasToken,
      note: hasAccount
        ? hasToken
          ? 'Zalo OAuth token đã lưu vault'
          : 'Chưa có token — Connect Zalo trên tab Channels'
        : 'Chưa có channel Zalo — thêm trên tab Channels',
    },
    {
      key: 'zalo_form_ids_configured',
      passed: formIds.length > 0,
      note:
        formIds.length > 0
          ? `Form IDs: ${formIds.join(', ')}`
          : 'Cấu hình form_ids trên channel Zalo hoặc /zalo/leads',
    },
  ];
}

export function parseZaloAccountRow(row: {
  has_account?: boolean | null;
  has_token?: boolean | null;
  meta_json?: unknown;
} | null): ZaloChannelAccountRow | null {
  if (!row?.has_account) return null;
  const formIds = readFormIdsFromMeta(row.meta_json) ?? [];
  return {
    has_account: true,
    has_token: Boolean(row.has_token),
    form_ids: formIds,
  };
}

export function normalizeCreativeChannelTag(value: string | undefined | null): string {
  return normalizeCreativeChannel(value);
}
