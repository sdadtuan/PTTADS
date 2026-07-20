const FIELD_KEY_RE = /^[a-z0-9_]+(?:-[a-z0-9_]+)*$/;

export function normalizeIndustryTraits(raw: unknown): Record<string, unknown> {
  if (raw == null) {
    return {};
  }
  let obj: unknown = raw;
  if (typeof raw === 'string') {
    const text = raw.trim();
    if (!text) return {};
    try {
      obj = JSON.parse(text);
    } catch {
      throw new Error('traits_json không hợp lệ — kiểm tra cú pháp JSON.');
    }
  }
  if (typeof obj !== 'object' || obj === null || Array.isArray(obj)) {
    throw new Error('traits phải là object JSON.');
  }
  const src = obj as Record<string, unknown>;
  const out: Record<string, unknown> = {};
  if ('addon_key' in src) {
    const key = String(src.addon_key ?? '')
      .trim()
      .slice(0, 80);
    if (key && !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(key)) {
      throw new Error('addon_key không hợp lệ.');
    }
    out.addon_key = key;
  }
  if ('addon_label' in src) {
    out.addon_label = String(src.addon_label ?? '')
      .trim()
      .slice(0, 200);
  }
  if ('fields' in src) {
    const fields = src.fields;
    if (fields == null) {
      out.fields = [];
    } else if (!Array.isArray(fields)) {
      throw new Error('fields phải là mảng.');
    } else {
      const normFields: Record<string, unknown>[] = [];
      const seen = new Set<string>();
      for (const item of fields) {
        if (typeof item !== 'object' || item === null) {
          throw new Error('Mỗi field add-on phải là object.');
        }
        const row = item as Record<string, unknown>;
        const fkey = String(row.key ?? '').trim();
        if (!fkey || !FIELD_KEY_RE.test(fkey)) {
          throw new Error(`Field key không hợp lệ: ${fkey || '(trống)'}`);
        }
        if (seen.has(fkey)) {
          throw new Error(`Field key trùng: ${fkey}`);
        }
        seen.add(fkey);
        const ftype = String(row.type ?? 'text')
          .trim()
          .toLowerCase();
        if (ftype !== 'text' && ftype !== 'select') {
          throw new Error(`Field type không hỗ trợ: ${ftype}`);
        }
        const field: Record<string, unknown> = {
          key: fkey,
          label: String(row.label ?? fkey)
            .trim()
            .slice(0, 200),
          type: ftype,
        };
        if (ftype === 'select') {
          const opts = row.options;
          if (!Array.isArray(opts) || !opts.length) {
            throw new Error(`Field ${fkey} (select) cần options.`);
          }
          field.options = opts
            .filter((o): o is Record<string, unknown> => typeof o === 'object' && o !== null)
            .map((o) => ({
              value: String(o.value ?? '')
                .trim()
                .slice(0, 80),
              label: String(o.label ?? o.value ?? '')
                .trim()
                .slice(0, 200),
            }))
            .filter((o) => o.value);
          if (!(field.options as unknown[]).length) {
            throw new Error(`Field ${fkey} (select) cần ít nhất một option.`);
          }
        }
        normFields.push(field);
      }
      out.fields = normFields;
    }
  }
  return out;
}

export function industryTraitsFieldCount(traits: Record<string, unknown> | undefined): number {
  if (!traits || typeof traits !== 'object') return 0;
  const fields = traits.fields;
  return Array.isArray(fields) ? fields.length : 0;
}
