export const SEO_AEO_SCHEMA = 'seo_aeo';
export const AEO_QUESTION_SOURCE = 'aeo';

export function aeoScanStubMode(): boolean {
  const flag = (process.env.PTT_AEO_SCAN_STUB ?? '1').trim().toLowerCase();
  return flag !== '0' && flag !== 'false' && flag !== 'off';
}
