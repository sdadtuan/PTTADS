const SLUG_RE = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

export function normalizeCatalogSlug(raw: string): string {
  let s = String(raw ?? '')
    .trim()
    .toLowerCase();
  s = s.replace(/[^a-z0-9]+/g, '-');
  s = s.replace(/-{2,}/g, '-').replace(/^-|-$/g, '');
  return s.slice(0, 80);
}

export function validateCatalogSlug(raw: string): string {
  const key = normalizeCatalogSlug(raw);
  if (!key || !SLUG_RE.test(key)) {
    throw new Error('Slug không hợp lệ (chữ thường, số, dấu gạch ngang).');
  }
  return key;
}

export function catalogTs(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}
