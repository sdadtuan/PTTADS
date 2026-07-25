export const SEO_CMS_SCHEMA = 'seo_aeo';

export function cmsAutoPublishEnabled(): boolean {
  const raw = (process.env.PTT_SEO_CMS_AUTO_PUBLISH ?? '0').trim().toLowerCase();
  return raw === '1' || raw === 'true' || raw === 'yes';
}

export function cmsPilotSecret(): string {
  return (process.env.PTT_SEO_CMS_WEBHOOK_SECRET ?? '').trim();
}
