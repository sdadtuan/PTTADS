import { normalizeCatalogSlug, validateCatalogSlug } from './catalog-slug.util';

describe('catalog-slug.util', () => {
  it('normalizes slug', () => {
    expect(normalizeCatalogSlug('  Foo Bar  ')).toBe('foo-bar');
  });

  it('validates slug', () => {
    expect(validateCatalogSlug('lead-gen')).toBe('lead-gen');
    expect(() => validateCatalogSlug('!!!')).toThrow();
  });
});
