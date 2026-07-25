export type CreativeChannel = 'meta' | 'google' | 'zalo';

const VALID_CHANNELS = new Set<CreativeChannel>(['meta', 'google', 'zalo']);

export function normalizeCreativeChannel(value: string | undefined | null): CreativeChannel {
  const ch = String(value ?? 'meta')
    .trim()
    .toLowerCase();
  if (VALID_CHANNELS.has(ch as CreativeChannel)) {
    return ch as CreativeChannel;
  }
  return 'meta';
}
