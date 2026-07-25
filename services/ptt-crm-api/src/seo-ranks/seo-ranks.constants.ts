export const SEO_RANKS_SCHEMA = 'seo_aeo';

export function serpProvider(): string {
  return (process.env.PTT_SERP_PROVIDER ?? 'stub').trim().toLowerCase();
}

export function serpStubMode(): boolean {
  const provider = serpProvider();
  if (provider === 'stub') return true;
  if (provider === 'serpapi') {
    return !(process.env.SERPAPI_API_KEY ?? process.env.PTT_SERPAPI_API_KEY ?? '').trim();
  }
  if (provider === 'dataforseo') {
    const login = (process.env.DATAFORSEO_LOGIN ?? process.env.PTT_DATAFORSEO_LOGIN ?? '').trim();
    const password = (process.env.DATAFORSEO_PASSWORD ?? process.env.PTT_DATAFORSEO_PASSWORD ?? '').trim();
    return !(login && password);
  }
  return true;
}
