export function defaultBusinessPlan(): Record<string, unknown> {
  return {
    vision: '',
    mission: '',
    strategic_goals: [],
    value_proposition: '',
    product_positioning: '',
    swot: { strengths: [], weaknesses: [], opportunities: [], threats: [] },
    target_market: '',
    competitive_advantage: '',
    market_analysis: {
      market_size_notes: '',
      demand_supply_notes: '',
      price_trend_notes: '',
      competitors: [],
    },
    pestel: {
      political: '',
      economic: '',
      social: '',
      technology: '',
      environment: '',
      legal: '',
    },
    customer_analysis: {
      primary_persona: '',
      secondary_persona: '',
      buyer_journey: '',
      decision_factors: [],
    },
    revenue_target_vnd: 0,
    cost_structure_notes: '',
    financial_plan: {
      total_investment_vnd: 0,
      land_cost_vnd: 0,
      construction_cost_vnd: 0,
      marketing_cost_vnd: 0,
      sales_cost_vnd: 0,
      profit_margin_target_pct: 0,
      cash_flow_notes: '',
    },
    break_even_units: 0,
    break_even_month: '',
    milestones: [],
    gantt_phases: [],
    approval_status: 'draft',
    notes: '',
  };
}

export function defaultMarketingPlan(): Record<string, unknown> {
  return {
    objectives: [],
    stp: {
      segmentation_criteria: '',
      primary_target: '',
      secondary_target: '',
      differentiation: '',
    },
    target_segments: [],
    positioning: '',
    key_messages: [],
    brand_guidelines: '',
    marketing_mix: {
      product_notes: '',
      price_notes: '',
      place_notes: '',
      promotion_notes: '',
    },
    competitor_marketing: '',
    funnel: {
      awareness_target: 0,
      mql_target_monthly: 0,
      site_visit_target_monthly: 0,
      booking_target_monthly: 0,
      conversion_lead_to_visit_pct: 0,
      conversion_visit_to_book_pct: 0,
    },
    channels: [],
    budget_breakdown: [],
    content_themes: [],
    creative_direction: '',
    campaigns: [],
    lead_target_monthly: 0,
    cpl_target_vnd: 0,
    budget_total_vnd: 0,
    kpi_marketing: {
      reach_target: 0,
      engagement_rate_pct: 0,
      cac_target_vnd: 0,
      roi_target_pct: 0,
    },
    launch_timeline: [],
    approval_status: 'draft',
    notes: '',
  };
}

export function defaultSalesPlan(): Record<string, unknown> {
  return {
    revenue_target_vnd: 0,
    units_target: 0,
    avg_price_target_vnd: 0,
    monthly_targets: [],
    pricing_strategy: '',
    commission_policy: '',
    channel_mix: { direct_pct: 60, agent_pct: 30, online_pct: 10 },
    sales_process: [],
    team_structure: [],
    incentive_programs: [],
    approval_status: 'draft',
    notes: '',
  };
}

export function parseJsonPlan(raw: string, fallback: Record<string, unknown>): Record<string, unknown> {
  try {
    const obj = JSON.parse(raw || '{}');
    return obj && typeof obj === 'object' && !Array.isArray(obj) ? (obj as Record<string, unknown>) : { ...fallback };
  } catch {
    return { ...fallback };
  }
}

export function mergePlan(
  stored: Record<string, unknown> | null | undefined,
  defaultPlan: Record<string, unknown>,
): Record<string, unknown> {
  const out = JSON.parse(JSON.stringify(defaultPlan)) as Record<string, unknown>;
  for (const [k, v] of Object.entries(stored ?? {})) {
    if (k in out && typeof out[k] === 'object' && out[k] !== null && !Array.isArray(out[k]) && typeof v === 'object' && v !== null && !Array.isArray(v)) {
      out[k] = { ...(out[k] as Record<string, unknown>), ...(v as Record<string, unknown>) };
    } else {
      out[k] = v !== null && typeof v === 'object' ? JSON.parse(JSON.stringify(v)) : v;
    }
  }
  return out;
}

export function slugTypeCode(raw: string): string {
  let s = String(raw ?? '')
    .trim()
    .toLowerCase();
  s = s.replace(/[^a-z0-9]+/g, '_');
  s = s.replace(/_+/g, '_').replace(/^_|_$/g, '');
  return s.slice(0, 40);
}
