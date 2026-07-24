import { MetaTrackingRepository } from './meta-tracking.repository';

export const META_LAUNCH_QA_CHECKLIST_ITEMS: Record<
  string,
  { label: string; completed: boolean; completed_by?: string; note?: string }
> = {
  meta_pixel_configured: { label: 'Pixel ID đã cấu hình', completed: false },
  meta_capi_test_ok: { label: 'CAPI test event OK', completed: false },
  meta_hub_map_coverage: { label: 'Hub map ≥80% spend', completed: false },
  meta_capi_recent_sent: { label: 'CAPI sent trong 48h', completed: false },
};

export const META_LAUNCH_QA_ITEM_KEYS = Object.keys(META_LAUNCH_QA_CHECKLIST_ITEMS);

export function isMetaLaunchQaEnabled(): boolean {
  return ['1', 'true', 'yes', 'on'].includes(
    (process.env.PTT_META_TRACKING_ENABLED ?? '0').trim().toLowerCase(),
  );
}

export function isMetaLaunchQaStrict(): boolean {
  return ['1', 'true', 'yes', 'on'].includes(
    (process.env.PTT_LAUNCH_QA_META_STRICT ?? '0').trim().toLowerCase(),
  );
}

export function isMetaLaunchQaItemKey(itemKey: string): boolean {
  return META_LAUNCH_QA_ITEM_KEYS.includes(itemKey.trim());
}

export function mergeMetaLaunchQaChecklist<T extends Record<string, unknown>>(
  checklist: T,
): T & typeof META_LAUNCH_QA_CHECKLIST_ITEMS {
  if (!isMetaLaunchQaEnabled()) {
    return checklist as T & typeof META_LAUNCH_QA_CHECKLIST_ITEMS;
  }
  const merged = { ...checklist } as T & typeof META_LAUNCH_QA_CHECKLIST_ITEMS;
  for (const [key, template] of Object.entries(META_LAUNCH_QA_CHECKLIST_ITEMS)) {
    if (!(key in merged)) {
      merged[key as keyof typeof merged] = { ...template } as (typeof merged)[keyof typeof merged];
    }
  }
  return merged;
}

export interface MetaLaunchQaEvalItem {
  key: string;
  passed: boolean;
  note: string;
}

function parseMeta(raw: unknown): Record<string, unknown> {
  if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
    return raw as Record<string, unknown>;
  }
  return {};
}

function pixelTestOkWithin7d(meta: Record<string, unknown>): boolean {
  const raw = meta.pixel_test_ok_at ?? meta.last_pixel_test_at;
  if (!raw) return false;
  const ts = new Date(String(raw)).getTime();
  if (!Number.isFinite(ts)) return false;
  return Date.now() - ts <= 7 * 24 * 60 * 60 * 1000;
}

export async function evaluateMetaLaunchQaItems(
  repo: MetaTrackingRepository,
  clientId: string,
): Promise<MetaLaunchQaEvalItem[]> {
  const cid = clientId.trim();
  if (!cid) return [];

  const [accounts, mapCoverage, lastSentAt] = await Promise.all([
    repo.listTrackingAccounts(cid),
    repo.computeUnmappedSpendPct(cid, 7),
    repo.getLastCapiSentAt(cid),
  ]);

  const account = accounts[0];
  const meta = account ? parseMeta(await repo.getChannelAccountMetaJson(cid)) : {};
  const pixelId = account?.pixel_id?.trim() || null;

  const pixelConfigured = Boolean(pixelId);
  const capiTestOk = pixelTestOkWithin7d(meta);
  const unmappedPct = mapCoverage.unmapped_spend_pct;
  const hubMapOk =
    mapCoverage.total_spend <= 0
      ? true
      : unmappedPct != null && unmappedPct <= 20;
  const strict = isMetaLaunchQaStrict();
  const recentSentOk =
    !strict ||
    (lastSentAt != null && Date.now() - new Date(lastSentAt).getTime() <= 48 * 60 * 60 * 1000);

  return [
    {
      key: 'meta_pixel_configured',
      passed: pixelConfigured,
      note: pixelConfigured
        ? `Pixel ${pixelId}`
        : 'Chưa cấu hình pixel_id trên channel account Meta',
    },
    {
      key: 'meta_capi_test_ok',
      passed: capiTestOk,
      note: capiTestOk
        ? 'Test pixel OK trong 7 ngày gần nhất'
        : 'Chạy Test pixel trên tab Tracking hoặc /meta/tracking',
    },
    {
      key: 'meta_hub_map_coverage',
      passed: hubMapOk,
      note:
        mapCoverage.total_spend <= 0
          ? 'Chưa có spend 7d — bỏ qua tạm'
          : hubMapOk
            ? `Unmapped spend ${unmappedPct?.toFixed(1) ?? '0'}% ≤ 20%`
            : `Unmapped spend ${unmappedPct?.toFixed(1) ?? '100'}% > 20% — map campaign trên Hub`,
    },
    {
      key: 'meta_capi_recent_sent',
      passed: recentSentOk,
      note: strict
        ? lastSentAt
          ? `CAPI sent lần cuối ${lastSentAt.slice(0, 16).replace('T', ' ')} UTC`
          : 'Chưa có CAPI sent — bật CAPI pilot hoặc chờ webhook'
        : 'Tuỳ chọn (PTT_LAUNCH_QA_META_STRICT=0)',
    },
  ];
}
