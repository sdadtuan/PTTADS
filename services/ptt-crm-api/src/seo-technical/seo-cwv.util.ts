function cwvRating(lcpMs: number | null, cls: number | null, inpMs: number | null): string {
  if (lcpMs == null && cls == null && inpMs == null) return 'unknown';
  let fails = 0;
  let checks = 0;
  if (lcpMs != null) {
    checks += 1;
    if (lcpMs > 2500) fails += 1;
  }
  if (cls != null) {
    checks += 1;
    if (cls > 0.1) fails += 1;
  }
  if (inpMs != null) {
    checks += 1;
    if (inpMs > 200) fails += 1;
  }
  if (checks === 0) return 'unknown';
  return fails ? 'fail' : 'pass';
}

export function parsePageSpeedResponse(data: Record<string, unknown>): {
  lcp_ms: number | null;
  cls: number | null;
  inp_ms: number | null;
  performance_score: number | null;
  cwv_rating: string;
} {
  const lh = (data.lighthouseResult ?? {}) as Record<string, unknown>;
  const audits = (lh.audits ?? {}) as Record<string, Record<string, unknown>>;
  const categories = (lh.categories ?? {}) as Record<string, Record<string, unknown>>;
  const perf = categories.performance ?? {};
  const auditValue = (key: string): number | null => {
    const raw = audits[key]?.numericValue;
    if (raw == null) return null;
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
  };
  const lcp = auditValue('largest-contentful-paint');
  const cls = auditValue('cumulative-layout-shift');
  const inp =
    auditValue('interaction-to-next-paint') ??
    auditValue('experimental-interaction-to-next-paint');
  const scoreRaw = perf.score;
  const performanceScore =
    scoreRaw != null && Number.isFinite(Number(scoreRaw)) ? Number(scoreRaw) * 100 : null;
  return {
    lcp_ms: lcp,
    cls,
    inp_ms: inp,
    performance_score: performanceScore,
    cwv_rating: cwvRating(lcp, cls, inp),
  };
}

export async function fetchPageSpeed(url: string, strategy = 'mobile'): Promise<Record<string, unknown>> {
  const apiKey = (
    process.env.PAGESPEED_API_KEY ??
    process.env.GOOGLE_PAGESPEED_API_KEY ??
    process.env.GOOGLE_API_KEY ??
    ''
  ).trim();
  if (!apiKey) throw new Error('pagespeed_api_key_missing');
  const qs = new URLSearchParams({
    url,
    strategy,
    category: 'performance',
    key: apiKey,
  });
  const resp = await fetch(`https://pagespeedonline.googleapis.com/pagespeedonline/v5/runPagespeed?${qs}`, {
    method: 'GET',
    signal: AbortSignal.timeout(90000),
  });
  if (!resp.ok) {
    const body = (await resp.text()).slice(0, 300);
    throw new Error(`pagespeed_http_${resp.status}: ${body}`);
  }
  const payload = (await resp.json()) as Record<string, unknown>;
  const metrics = parsePageSpeedResponse(payload);
  return { ...metrics, source: 'pagespeed', url };
}

export function stubPageSpeed(url: string): Record<string, unknown> {
  return {
    url,
    lcp_ms: 2100,
    cls: 0.05,
    inp_ms: 180,
    performance_score: 82,
    cwv_rating: 'pass',
    source: 'stub',
  };
}

export async function effectivePageSpeed(url: string): Promise<Record<string, unknown>> {
  const stub = (process.env.PTT_CWV_STUB ?? '0').trim().toLowerCase();
  if (['1', 'true', 'yes'].includes(stub)) return stubPageSpeed(url);
  return fetchPageSpeed(url);
}
