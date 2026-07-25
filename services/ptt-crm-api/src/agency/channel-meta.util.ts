export function parseFormIds(raw: string | string[] | null | undefined): string[] | undefined {
  if (raw === undefined) return undefined;
  if (raw === null) return [];
  if (Array.isArray(raw)) {
    return raw.map((item) => String(item).trim()).filter(Boolean);
  }
  const text = String(raw).trim();
  if (!text) return [];
  return text
    .split(/[,;\n]+/)
    .map((part) => part.trim())
    .filter(Boolean);
}

export function channelAccountMetaPatch(
  channel: string,
  params: { facebook_page_id?: string; form_ids?: string[] | undefined },
): Record<string, unknown> | null {
  const ch = channel.trim().toLowerCase();
  const patch: Record<string, unknown> = {};

  const pagePatch = metaPagePatch(ch, params.facebook_page_id);
  if (pagePatch) Object.assign(patch, pagePatch);

  if (ch === 'zalo' && params.form_ids !== undefined) {
    patch.form_ids = params.form_ids;
  }

  return Object.keys(patch).length ? patch : null;
}

function metaPagePatch(channel: string, facebookPageId?: string): Record<string, string> | null {
  if (channel.trim().toLowerCase() !== 'meta') return null;
  const pageId = normMetaPageId(facebookPageId ?? '');
  if (!pageId) return null;
  return { facebook_page_id: pageId, page_id: pageId };
}

function normMetaPageId(raw: string): string | null {
  const id = String(raw ?? '')
    .replace(/\D/g, '')
    .trim();
  return id || null;
}

export function readFormIdsFromMeta(meta: unknown): string[] | null {
  if (!meta || typeof meta !== 'object') return null;
  const raw = (meta as Record<string, unknown>).form_ids;
  if (!Array.isArray(raw)) return null;
  const ids = raw.map((item) => String(item).trim()).filter(Boolean);
  return ids.length ? ids : [];
}
