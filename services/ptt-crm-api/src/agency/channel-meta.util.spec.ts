import { channelAccountMetaPatch, parseFormIds, readFormIdsFromMeta } from './channel-meta.util';

describe('channel-meta.util', () => {
  it('parseFormIds splits comma and newline lists', () => {
    expect(parseFormIds('form_a, form_b;form_c')).toEqual(['form_a', 'form_b', 'form_c']);
    expect(parseFormIds(['x', ' y '])).toEqual(['x', 'y']);
    expect(parseFormIds('')).toEqual([]);
    expect(parseFormIds(undefined)).toBeUndefined();
  });

  it('channelAccountMetaPatch stores zalo form_ids in meta', () => {
    expect(channelAccountMetaPatch('zalo', { form_ids: ['f1', 'f2'] })).toEqual({
      form_ids: ['f1', 'f2'],
    });
    expect(channelAccountMetaPatch('meta', { facebook_page_id: '123456789' })).toEqual({
      facebook_page_id: '123456789',
      page_id: '123456789',
    });
  });

  it('readFormIdsFromMeta reads array from meta json', () => {
    expect(readFormIdsFromMeta({ form_ids: ['a', 'b'] })).toEqual(['a', 'b']);
    expect(readFormIdsFromMeta({})).toBeNull();
  });
});
