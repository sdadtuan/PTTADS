export type AttributionModel = 'last_touch_crm';
export type SpendSource = 'meta_api';

export interface MetaDataFreshness {
  through_date: string;
  synced_at: string | null;
}

export interface MetaAttributionMeta {
  attribution_model: AttributionModel;
  unmapped_spend_pct: number;
  spend_source: SpendSource;
  data_freshness: MetaDataFreshness;
}

export function roundPct(value: number): number {
  return Math.round(value * 10) / 10;
}

export function computeUnmappedSpendPct(unmappedSpend: number, totalSpend: number): number {
  if (totalSpend <= 0) return 0;
  return roundPct((unmappedSpend / totalSpend) * 100);
}

export function computeCplDelta(
  cpl: number | null,
  target: number | null,
): { deltaVnd: number | null; deltaPct: number | null; overTarget: boolean } {
  if (cpl == null || target == null || target <= 0) {
    return { deltaVnd: null, deltaPct: null, overTarget: false };
  }
  const deltaVnd = Math.round((cpl - target) * 100) / 100;
  const deltaPct = Math.round(((cpl - target) / target) * 1000) / 10;
  return { deltaVnd, deltaPct, overTarget: cpl > target };
}

export function buildMetaAttributionMeta(params: {
  dateTo: string;
  syncedAt: string | null;
  unmappedSpendPct: number;
}): MetaAttributionMeta {
  return {
    attribution_model: 'last_touch_crm',
    unmapped_spend_pct: params.unmappedSpendPct,
    spend_source: 'meta_api',
    data_freshness: {
      through_date: params.dateTo,
      synced_at: params.syncedAt,
    },
  };
}
