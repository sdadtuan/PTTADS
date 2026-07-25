export function seoHubEnabled(): boolean {
  const raw = process.env.NEXT_PUBLIC_PTT_SEO_HUB_ENABLED ?? '1';
  return raw.trim().toLowerCase() !== '0';
}

export function seoClientWorkspaceEnabled(): boolean {
  const raw = process.env.NEXT_PUBLIC_PTT_SEO_CLIENT_WORKSPACE_ENABLED ?? '1';
  return raw.trim().toLowerCase() !== '0';
}

export function seoResearchEnabled(): boolean {
  const raw = process.env.NEXT_PUBLIC_PTT_SEO_RESEARCH_ENABLED ?? '1';
  return raw.trim().toLowerCase() !== '0';
}

export function seoContentEnabled(): boolean {
  const raw = process.env.NEXT_PUBLIC_PTT_SEO_CONTENT_ENABLED ?? '1';
  return raw.trim().toLowerCase() !== '0';
}

export function seoTechnicalEnabled(): boolean {
  const raw = process.env.NEXT_PUBLIC_PTT_SEO_TECHNICAL_ENABLED ?? '1';
  return raw.trim().toLowerCase() !== '0';
}

export function seoReportsEnabled(): boolean {
  const raw = process.env.NEXT_PUBLIC_PTT_SEO_REPORTS_ENABLED ?? '1';
  return raw.trim().toLowerCase() !== '0';
}

export function seoGovernanceEnabled(): boolean {
  const raw = process.env.NEXT_PUBLIC_PTT_SEO_GOVERNANCE_ENABLED ?? '1';
  return raw.trim().toLowerCase() !== '0';
}

export function seoStrategyEnabled(): boolean {
  const raw = process.env.NEXT_PUBLIC_PTT_SEO_STRATEGY_ENABLED ?? '1';
  return raw.trim().toLowerCase() !== '0';
}

export function seoAeoEnabled(): boolean {
  const raw = process.env.NEXT_PUBLIC_PTT_SEO_AEO_ENABLED ?? '1';
  return raw.trim().toLowerCase() !== '0';
}

export function seoAuthorityEnabled(): boolean {
  const raw = process.env.NEXT_PUBLIC_PTT_SEO_AUTHORITY_ENABLED ?? '1';
  return raw.trim().toLowerCase() !== '0';
}

export function seoRanksEnabled(): boolean {
  const raw = process.env.NEXT_PUBLIC_PTT_SEO_RANKS_ENABLED ?? '1';
  return raw.trim().toLowerCase() !== '0';
}

export function seoAutomationsEnabled(): boolean {
  const raw = process.env.NEXT_PUBLIC_PTT_SEO_AUTOMATIONS_ENABLED ?? '1';
  return raw.trim().toLowerCase() !== '0';
}

export function seoFreshnessEnabled(): boolean {
  const raw = process.env.NEXT_PUBLIC_PTT_SEO_FRESHNESS_ENABLED ?? '1';
  return raw.trim().toLowerCase() !== '0';
}

export function seoExperimentsEnabled(): boolean {
  const raw = process.env.NEXT_PUBLIC_PTT_SEO_EXPERIMENTS_ENABLED ?? '0';
  return raw.trim().toLowerCase() !== '0' && raw.trim().toLowerCase() !== 'false';
}
