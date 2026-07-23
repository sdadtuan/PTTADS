import { extractMetaLeadgenContext } from './meta-webhook-context';

describe('extractMetaLeadgenContext', () => {
  it('returns empty arrays for non-entry payload', () => {
    expect(extractMetaLeadgenContext({ object: 'page' })).toEqual({
      pageIds: [],
      formIds: [],
      leadgenIds: [],
    });
  });

  it('extracts page, form, and leadgen ids from leadgen changes', () => {
    const ctx = extractMetaLeadgenContext({
      object: 'page',
      entry: [
        {
          id: '123456789012345',
          changes: [
            {
              field: 'leadgen',
              value: {
                page_id: '123456789012345',
                form_id: '2814926042203269',
                leadgen_id: '987654321098765',
              },
            },
          ],
        },
      ],
    });
    expect(ctx.pageIds).toEqual(['123456789012345']);
    expect(ctx.formIds).toEqual(['2814926042203269']);
    expect(ctx.leadgenIds).toEqual(['987654321098765']);
  });

  it('ignores non-leadgen changes', () => {
    const ctx = extractMetaLeadgenContext({
      entry: [{ id: '111', changes: [{ field: 'feed', value: {} }] }],
    });
    expect(ctx.pageIds).toEqual(['111']);
    expect(ctx.formIds).toEqual([]);
    expect(ctx.leadgenIds).toEqual([]);
  });
});
