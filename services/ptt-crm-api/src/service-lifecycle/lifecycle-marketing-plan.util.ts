export const TARGET_MARKET_PROF_KEYS = [
  'market_context',
  'tam_sam_som',
  'geo_behavior',
  'segmentation_icp',
  'personas_roles',
  'jobs_to_be_done',
  'pains_desired_outcomes',
  'buy_triggers_obstacles',
  'criteria_vs_alternatives',
  'insights_evidence',
  'segment_priorities',
  'success_hypotheses_next',
] as const;

export const OFFICIAL_TMMT_CORE_KEYS = [
  'market_context',
  'segmentation_icp',
  'personas_roles',
  'pains_desired_outcomes',
] as const;

export const OFFICIAL_TMMT_MIN_FILLED = 6;

export function parsePlanContent(plan: Record<string, unknown> | null): {
  strategy_framework: Record<string, string>;
  target_market_prof: Record<string, string>;
} {
  let sf: Record<string, string> = {};
  let prof: Record<string, string> = {};
  try {
    sf = JSON.parse(String(plan?.strategy_framework_json ?? '{}')) as Record<string, string>;
  } catch {
    sf = {};
  }
  try {
    prof = JSON.parse(String(plan?.target_market_prof_json ?? '{}')) as Record<string, string>;
  } catch {
    prof = {};
  }
  return { strategy_framework: sf, target_market_prof: prof };
}

export function validateOfficialTmmt(plan: Record<string, unknown> | null): {
  ok: boolean;
  complete: boolean;
  messages: string[];
} {
  if (!plan) {
    return {
      ok: false,
      complete: false,
      messages: ['Chưa có Kế hoạch MKT chính thức trên lifecycle.'],
    };
  }
  const { strategy_framework: sf, target_market_prof: prof } = parsePlanContent(plan);
  const messages: string[] = [];
  if (!String(sf.target_market ?? '').trim()) {
    messages.push('Điền TMMT tóm tắt (target_market) trong khung chiến lược.');
  }
  for (const key of OFFICIAL_TMMT_CORE_KEYS) {
    if (!String(prof[key] ?? '').trim()) {
      messages.push(`Điền TMMT chi tiết: ${key}.`);
    }
  }
  const filled = TARGET_MARKET_PROF_KEYS.filter((k) => String(prof[k] ?? '').trim()).length;
  if (filled < OFFICIAL_TMMT_MIN_FILLED) {
    messages.push(
      `TMMT chi tiết cần ít nhất ${OFFICIAL_TMMT_MIN_FILLED} mục (hiện ${filled}/${TARGET_MARKET_PROF_KEYS.length}).`,
    );
  }
  return { ok: messages.length === 0, complete: messages.length === 0, messages };
}
