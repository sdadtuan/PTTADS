export function stubSerpResults(phrase: string, domainHint = ''): Array<{
  position: number;
  title: string;
  url: string;
  snippet: string;
}> {
  const base = domainHint || 'example.com';
  return [
    { position: 1, title: `${phrase} — Top result`, url: `https://${base}/`, snippet: 'Stub SERP #1' },
    { position: 2, title: `Guide: ${phrase}`, url: 'https://competitor-a.com/p', snippet: 'Stub SERP #2' },
    { position: 3, title: `${phrase} FAQ`, url: 'https://competitor-b.com/faq', snippet: 'Stub SERP #3' },
  ];
}

export function domainMatch(url: string, domainHint: string): boolean {
  if (!url || !domainHint) return false;
  try {
    const host = new URL(url.includes('://') ? url : `https://${url}`).hostname.toLowerCase();
    const hint = domainHint.toLowerCase().replace(/^https?:\/\//, '').split('/')[0] ?? '';
    return host.includes(hint) || host.endsWith(`.${hint}`);
  } catch {
    return false;
  }
}

export function positionForDomain(
  results: Array<{ position?: number; url?: string }>,
  domainHint: string,
): { position: number | null; url: string } {
  for (const row of results) {
    const url = String(row.url ?? '');
    if (domainMatch(url, domainHint)) {
      const pos = row.position;
      return { position: pos != null && Number.isFinite(Number(pos)) ? Number(pos) : null, url };
    }
  }
  return { position: null, url: '' };
}

export async function fetchSerpResults(
  phrase: string,
  domainHint = '',
): Promise<{ results: Array<{ position: number; title: string; url: string; snippet: string }>; source: string }> {
  return { results: stubSerpResults(phrase, domainHint), source: 'stub' };
}
