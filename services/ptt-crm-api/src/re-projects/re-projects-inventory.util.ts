import {
  KPI_CATEGORY_LABELS,
  PRODUCT_LINE_LABELS,
  PRODUCT_TYPOLOGY_LABELS,
} from './re-projects.types';

export function computeProductInventoryStats(products: Array<Record<string, unknown>>): Record<string, unknown> {
  const byLine: Record<string, Record<string, unknown>> = {};
  const byZone: Record<string, Record<string, unknown>> = {};
  const byTypology: Record<string, Record<string, unknown>> = {};
  const byStatus: Record<string, number> = {};
  let totalValue = 0;
  let availableValue = 0;

  for (const p of products) {
    const line = String(p.product_line || 'other') || 'other';
    const zone = String(p.zone || '').trim() || 'Chưa phân khu';
    const typo = String(p.typology || 'other') || 'other';
    const st = String(p.status || 'available');
    const price = Number(p.list_price_vnd ?? 0);
    totalValue += price;
    if (st === 'available') availableValue += price;
    byStatus[st] = (byStatus[st] ?? 0) + 1;

    for (const [bucket, key, labels] of [
      [byLine, line, PRODUCT_LINE_LABELS] as const,
      [byZone, zone, null] as const,
      [byTypology, typo, PRODUCT_TYPOLOGY_LABELS] as const,
    ]) {
      if (!bucket[key]) {
        const label = labels ? (labels[key] ?? key) : key;
        bucket[key] = {
          key,
          label,
          total: 0,
          available: 0,
          sold: 0,
          booked: 0,
          list_value_vnd: 0,
        };
      }
      const b = bucket[key];
      b.total = Number(b.total) + 1;
      if (st === 'available') b.available = Number(b.available) + 1;
      else if (st === 'sold') b.sold = Number(b.sold) + 1;
      else if (st === 'booked' || st === 'hold') b.booked = Number(b.booked) + 1;
      b.list_value_vnd = Number(b.list_value_vnd) + price;
    }
  }

  const sortBucket = (vals: Record<string, Record<string, unknown>>) =>
    Object.values(vals).sort((a, b) => Number(b.total) - Number(a.total) || String(a.label).localeCompare(String(b.label)));

  return {
    total: products.length,
    available: products.filter((p) => p.status === 'available').length,
    sold: products.filter((p) => p.status === 'sold').length,
    booked: products.filter((p) => p.status === 'booked' || p.status === 'hold').length,
    total_list_value_vnd: totalValue,
    available_list_value_vnd: availableValue,
    by_product_line: sortBucket(byLine),
    by_zone: sortBucket(byZone),
    by_typology: sortBucket(byTypology),
    by_status: byStatus,
  };
}

export function computeKpiBoardStats(kpis: Array<Record<string, unknown>>): Record<string, unknown> {
  const byStaff: Record<string, Record<string, unknown>> = {};
  const byCategory: Record<string, Record<string, unknown>> = {};
  let weightTotal = 0;
  let achievementSum = 0;
  let withOwner = 0;

  for (const k of kpis) {
    const cat = String(k.category || 'sales');
    const sid = Number(k.owner_staff_id ?? 0);
    const ownerKey = sid > 0 ? String(sid) : String(k.owner_name || '').trim() || 'unassigned';
    const ownerLabel = String(k.owner_display || k.owner_name || 'Chưa gán');
    if (sid > 0 || String(k.owner_name || '').trim()) withOwner += 1;
    const weight = Number(k.weight_pct ?? 0);
    const ach = Number(k.achievement_pct ?? 0);
    weightTotal += weight;
    achievementSum += ach;

    if (!byStaff[ownerKey]) {
      byStaff[ownerKey] = {
        owner_key: ownerKey,
        owner_staff_id: sid || null,
        owner_name: ownerLabel,
        count: 0,
        weight_pct: 0,
        avg_achievement_pct: 0,
        _ach_sum: 0,
      };
    }
    byStaff[ownerKey].count = Number(byStaff[ownerKey].count) + 1;
    byStaff[ownerKey].weight_pct = Number(byStaff[ownerKey].weight_pct) + weight;
    byStaff[ownerKey]._ach_sum = Number(byStaff[ownerKey]._ach_sum) + ach;

    if (!byCategory[cat]) {
      byCategory[cat] = {
        category: cat,
        label: KPI_CATEGORY_LABELS[cat] ?? cat,
        count: 0,
        avg_achievement_pct: 0,
        _ach_sum: 0,
      };
    }
    byCategory[cat].count = Number(byCategory[cat].count) + 1;
    byCategory[cat]._ach_sum = Number(byCategory[cat]._ach_sum) + ach;
  }

  const staffRows: Array<Record<string, unknown>> = Object.values(byStaff).map((row) => {
    const cnt = Number(row.count) || 1;
    const { _ach_sum, ...rest } = row;
    return {
      ...rest,
      avg_achievement_pct: Math.round((Number(_ach_sum) / cnt) * 10) / 10,
      weight_pct: Math.round(Number(row.weight_pct) * 10) / 10,
    };
  });
  staffRows.sort(
    (a, b) =>
      Number(b.count) - Number(a.count) ||
      String(a.owner_name).localeCompare(String(b.owner_name)),
  );

  const catRows: Array<Record<string, unknown>> = Object.values(byCategory).map((row) => {
    const cnt = Number(row.count) || 1;
    const { _ach_sum, ...rest } = row;
    return {
      ...rest,
      avg_achievement_pct: Math.round((Number(_ach_sum) / cnt) * 10) / 10,
    };
  });
  catRows.sort(
    (a, b) => Number(b.count) - Number(a.count) || String(a.label).localeCompare(String(b.label)),
  );

  const n = kpis.length || 1;
  return {
    total: kpis.length,
    with_owner_count: withOwner,
    weight_total_pct: Math.round(weightTotal * 10) / 10,
    avg_achievement_pct: kpis.length ? Math.round((achievementSum / n) * 10) / 10 : 0,
    by_staff: staffRows,
    by_category: catRows,
  };
}
