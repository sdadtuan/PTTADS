export const PRELIMINARY_STRATEGY_KEYS = [
  'market_message',
  'media_reach',
  'conversion_strategy',
] as const;

export const PRELIMINARY_SUMMARY_FIELDS = ['north_star', 'objectives'] as const;

export const STRATEGY_FRAMEWORK_KEYS = [
  'target_market',
  'market_message',
  'media_reach',
  'retention_system',
  'nurture_system',
  'conversion_strategy',
  'world_class_experience',
  'lifecycle_extension',
  'referral_engine',
] as const;

export function defaultStrategyJson(): Record<string, string> {
  return Object.fromEntries(STRATEGY_FRAMEWORK_KEYS.map((k) => [k, '']));
}

export function validatePreliminaryPlan(plan: {
  name?: string | null;
  north_star?: string | null;
  objectives?: string | null;
  strategy_framework_json?: string | null;
} | null): { ok: boolean; complete: boolean; messages: string[] } {
  if (!plan) {
    return { ok: false, complete: false, messages: ['Chưa có Kế hoạch MKT sơ bộ — điền form Báo giá.'] };
  }
  const messages: string[] = [];
  const name = String(plan.name || '').trim();
  if (!name) messages.push('Nhập tên kế hoạch MKT sơ bộ.');
  if (!String(plan.north_star || '').trim() && !String(plan.objectives || '').trim()) {
    messages.push('Nhập North Star hoặc Mục tiêu chiến lược.');
  }
  let sf: Record<string, string> = {};
  try {
    sf = JSON.parse(String(plan.strategy_framework_json || '{}')) as Record<string, string>;
  } catch {
    sf = {};
  }
  for (const key of PRELIMINARY_STRATEGY_KEYS) {
    if (!String(sf[key] || '').trim()) {
      messages.push(`Điền khối chiến lược: ${key}.`);
    }
  }
  return { ok: messages.length === 0, complete: messages.length === 0, messages };
}

export function planContentFromRow(plan: Record<string, unknown>): {
  name: string;
  north_star: string;
  objectives: string;
  strategy_framework: Record<string, string>;
} {
  let sf: Record<string, string> = {};
  try {
    sf = JSON.parse(String(plan.strategy_framework_json || '{}')) as Record<string, string>;
  } catch {
    sf = {};
  }
  return {
    name: String(plan.name || ''),
    north_star: String(plan.north_star || ''),
    objectives: String(plan.objectives || ''),
    strategy_framework: sf,
  };
}
