export const SEO_GATE_A_SCHEMA = 'seo_aeo';

export function governanceEnabled(): boolean {
  const raw = (process.env.PTT_SEO_GOVERNANCE_ENABLED ?? '1').trim().toLowerCase();
  return raw !== '0' && raw !== 'false' && raw !== 'no';
}

export function portalSeoEnabled(): boolean {
  const raw = (process.env.PTT_PORTAL_SEO_ENABLED ?? '0').trim().toLowerCase();
  return raw === '1' || raw === 'true' || raw === 'yes';
}

export function experimentsEnabled(): boolean {
  const raw = (process.env.PTT_SEO_EXPERIMENTS_ENABLED ?? '0').trim().toLowerCase();
  return raw === '1' || raw === 'true' || raw === 'yes';
}

export const OPS_WEB_SEO_ROUTES = [
  '/seo/hub',
  '/seo/clients',
  '/seo/research',
  '/seo/content',
  '/seo/technical',
  '/seo/reports',
  '/seo/governance',
  '/seo/strategy',
  '/seo/aeo',
  '/seo/authority',
  '/seo/ranks',
  '/seo/automations',
  '/seo/freshness',
  '/seo/experiments',
  '/seo/bi',
  '/seo/cms',
  '/seo/gate-a',
] as const;

export const QA_HANDOFF_CHECKLIST: Array<{ id: string; label: string; automated?: boolean }> = [
  { id: 'client_settings', label: 'Client SEO settings → workspace visible' },
  { id: 'research_pipeline', label: 'Research → brief → pipeline card', automated: true },
  { id: 'approval_chain', label: 'Full approval chain content → published' },
  { id: 'crawl_import', label: 'Crawl import → issue → auto task', automated: true },
  { id: 'aeo_scan', label: 'AEO batch scan → coverage update' },
  { id: 'executive_drilldown', label: 'Executive drill-down ≤3 clicks' },
  { id: 'rbac_writer', label: 'RBAC — writer cannot approve', automated: true },
  { id: 'governance_block', label: 'Governance block publish without metadata' },
  { id: 'cwv_panel', label: 'CWV panel loads snapshots (S-09)' },
  { id: 'cms_autopublish', label: 'CMS auto-publish job on published (E5)' },
  { id: 'attribution_api', label: 'Attribution summary API (E7)' },
  { id: 'portal_e2e', label: 'Portal client review E2E', automated: true },
];
