export const SEO_BI_SCHEMA = 'seo_aeo';

export function clickhouseConfigured(): boolean {
  return Boolean(
    (process.env.CLICKHOUSE_URL ?? '').trim() || (process.env.CLICKHOUSE_HOST ?? '').trim(),
  );
}

export function seoBiExportEnabled(): boolean {
  const raw = (process.env.PTT_SEO_BI_EXPORT_ENABLED ?? '1').trim().toLowerCase();
  return raw !== '0' && raw !== 'false' && raw !== 'no';
}
