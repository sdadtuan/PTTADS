import {
  computeCpl,
  computeRoas,
  formatDateOnly,
  normalizePerformanceChannel,
  performanceChannelSql,
  resolveDateWindow,
} from './performance.util';

describe('performance.util', () => {
  it('normalizePerformanceChannel accepts meta aliases', () => {
    expect(normalizePerformanceChannel('meta')).toBe('meta');
    expect(normalizePerformanceChannel('facebook')).toBe('meta');
    expect(normalizePerformanceChannel('google')).toBe('google');
    expect(normalizePerformanceChannel('')).toBeNull();
    expect(normalizePerformanceChannel('tiktok')).toBeNull();
  });

  it('performanceChannelSql filters channels', () => {
    expect(performanceChannelSql('meta')).toEqual(['meta']);
    expect(performanceChannelSql('google')).toEqual(['google']);
    expect(performanceChannelSql(null)).toEqual(['meta', 'google']);
  });

  it('computeCpl returns null when no leads or spend', () => {
    expect(computeCpl(150000, 3)).toBe(50000);
    expect(computeCpl(1000, 0)).toBeNull();
    expect(computeCpl(0, 5)).toBeNull();
  });

  it('computeRoas handles zero conversion', () => {
    expect(computeRoas(300000, 150000)).toBe(2);
    expect(computeRoas(0, 150000)).toBeNull();
  });

  it('resolveDateWindow swaps inverted range', () => {
    const { start, end } = resolveDateWindow({ from: '2026-07-20', to: '2026-07-10' });
    expect(formatDateOnly(start)).toBe('2026-07-10');
    expect(formatDateOnly(end)).toBe('2026-07-20');
  });
});
