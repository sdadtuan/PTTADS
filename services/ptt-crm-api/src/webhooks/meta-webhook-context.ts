/** Extract Meta leadgen context from webhook JSON (no Graph calls). */

export interface MetaWebhookLeadgenContext {
  pageIds: string[];
  formIds: string[];
  leadgenIds: string[];
}

function normId(raw: unknown): string {
  return String(raw ?? '')
    .replace(/\D/g, '')
    .trim();
}

export function extractMetaLeadgenContext(payload: Record<string, unknown>): MetaWebhookLeadgenContext {
  const pageIds = new Set<string>();
  const formIds = new Set<string>();
  const leadgenIds = new Set<string>();

  const entries = payload.entry;
  if (!Array.isArray(entries)) {
    return { pageIds: [], formIds: [], leadgenIds: [] };
  }

  for (const entry of entries) {
    if (!entry || typeof entry !== 'object') continue;
    const entryPage = normId((entry as { id?: unknown }).id);
    if (entryPage) pageIds.add(entryPage);

    const changes = (entry as { changes?: unknown }).changes;
    if (!Array.isArray(changes)) continue;

    for (const change of changes) {
      if (!change || typeof change !== 'object') continue;
      const ch = change as { field?: string; value?: Record<string, unknown> };
      if (ch.field !== 'leadgen') continue;
      const val = ch.value ?? {};
      const pageId = normId(val.page_id);
      const formId = normId(val.form_id);
      const leadgenId = normId(val.leadgen_id);
      if (pageId) pageIds.add(pageId);
      if (formId) formIds.add(formId);
      if (leadgenId) leadgenIds.add(leadgenId);
    }
  }

  return {
    pageIds: [...pageIds],
    formIds: [...formIds],
    leadgenIds: [...leadgenIds],
  };
}
