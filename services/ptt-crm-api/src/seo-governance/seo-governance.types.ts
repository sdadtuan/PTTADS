export interface SeoGovernancePolicyRow {
  id: number;
  customer_id: number | null;
  policy_key: string;
  name: string;
  description: string;
  rule_type: string;
  rule_config: Record<string, unknown>;
  severity: string;
  active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface SeoGovernanceViolation {
  policy_key: string;
  name: string;
  severity: string;
  details: string[];
}

export interface SeoGovernanceEvaluateResult {
  ok: boolean;
  violations: SeoGovernanceViolation[];
  evaluation_id: number | null;
}

export interface SeoGovernanceComplianceSummary {
  customer_id: number | null;
  days: number;
  evaluations: number;
  passed: number;
  failed: number;
  pass_rate_pct: number;
}
