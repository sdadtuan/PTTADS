import { evaluateZaloLaunchQaItems } from './launch-qa-zalo.util';

describe('launch-qa-zalo.util', () => {
  it('evaluateZaloLaunchQaItems checks token and form ids', () => {
    const items = evaluateZaloLaunchQaItems({
      has_account: true,
      has_token: true,
      form_ids: ['f1'],
    });
    expect(items.find((i) => i.key === 'zalo_oauth_token')?.passed).toBe(true);
    expect(items.find((i) => i.key === 'zalo_form_ids_configured')?.passed).toBe(true);
  });

  it('fails when token missing', () => {
    const items = evaluateZaloLaunchQaItems({
      has_account: true,
      has_token: false,
      form_ids: [],
    });
    expect(items.find((i) => i.key === 'zalo_oauth_token')?.passed).toBe(false);
  });
});
