const SOURCE_URL_KEYS = ['referring page url', 'referring url', 'source url', 'source page', 'from url', 'url'];
const TARGET_URL_KEYS = ['target url', 'destination url', 'to url', 'landing page'];
const ANCHOR_KEYS = ['anchor', 'anchor text', 'link anchor'];
const DR_KEYS = ['domain rating', 'dr', 'domain rank', 'authority score'];
const DOMAIN_KEYS = ['referring domains', 'source domain', 'domain', 'referring domain'];
const STATUS_KEYS = ['status', 'link type', 'type'];

function normKey(key: string): string {
  return key.trim().toLowerCase().replace(/_/g, ' ').replace(/\s+/g, ' ');
}

function pick(row: Record<string, string>, keys: string[]): string {
  const normalized: Record<string, string> = {};
  for (const [k, v] of Object.entries(row)) {
    normalized[normKey(k)] = v;
  }
  for (const key of keys) {
    const val = normalized[key];
    if (val?.trim()) return val.trim();
  }
  return '';
}

function domainFromUrl(url: string): string {
  if (!url) return '';
  try {
    const host = new URL(url.includes('://') ? url : `https://${url}`).hostname.toLowerCase();
    return host.startsWith('www.') ? host.slice(4) : host;
  } catch {
    return url.split('/')[0]?.toLowerCase() ?? '';
  }
}

function parseDr(raw: string): number | null {
  const text = raw.trim().replace(',', '.');
  if (!text) return null;
  const n = Number.parseFloat(text);
  return Number.isFinite(n) ? n : null;
}

function inferStatus(raw: string): string {
  const text = raw.trim().toLowerCase();
  if (['lost', 'removed', 'broken', 'inactive'].includes(text)) return 'lost';
  if (['pending', 'new'].includes(text)) return 'pending';
  return 'active';
}

export function parseAuthorityCsv(
  csvText: string,
  signalType: string,
): { rows: Array<Record<string, unknown>>; skipped: number } {
  const lines = csvText.trim().split(/\r?\n/);
  if (lines.length < 2) return { rows: [], skipped: 0 };
  const headers = lines[0].split(',').map((h) => h.trim().replace(/^"|"$/g, ''));
  const rows: Array<Record<string, unknown>> = [];
  let skipped = 0;
  const today = new Date().toISOString().slice(0, 10);

  for (let i = 1; i < lines.length; i += 1) {
    const cols = lines[i].split(',').map((c) => c.trim().replace(/^"|"$/g, ''));
    const row: Record<string, string> = {};
    headers.forEach((h, idx) => {
      row[h] = cols[idx] ?? '';
    });
    const sourceUrl = pick(row, SOURCE_URL_KEYS);
    const targetUrl = pick(row, TARGET_URL_KEYS);
    if (!sourceUrl && !targetUrl) {
      skipped += 1;
      continue;
    }
    rows.push({
      signal_type: signalType,
      source_domain: pick(row, DOMAIN_KEYS) || domainFromUrl(sourceUrl),
      source_url: sourceUrl,
      target_url: targetUrl,
      anchor_text: pick(row, ANCHOR_KEYS),
      domain_rating: parseDr(pick(row, DR_KEYS)),
      status: inferStatus(pick(row, STATUS_KEYS)),
      first_seen_at: today,
      last_seen_at: today,
    });
  }
  return { rows, skipped };
}
