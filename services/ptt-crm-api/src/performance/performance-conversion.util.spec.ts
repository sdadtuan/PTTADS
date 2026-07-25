import {
  computeCpa,
  isWonLeadStatus,
  parseDealValueVnd,
} from './performance-conversion.util';

describe('performance-conversion.util', () => {
  it('isWonLeadStatus recognizes won variants', () => {
    expect(isWonLeadStatus('won')).toBe(true);
    expect(isWonLeadStatus('closed_won')).toBe(true);
    expect(isWonLeadStatus('Closed Won')).toBe(true);
    expect(isWonLeadStatus('lost')).toBe(false);
    expect(isWonLeadStatus('qualified')).toBe(false);
  });

  it('parseDealValueVnd reads meta fields', () => {
    expect(parseDealValueVnd({ deal_value_vnd: '1,500,000' })).toBe(1500000);
    expect(parseDealValueVnd({ deal_value: 2000000 })).toBe(2000000);
    expect(parseDealValueVnd({})).toBe(0);
  });

  it('computeCpa divides spend by won count', () => {
    expect(computeCpa(1000000, 2)).toBe(500000);
    expect(computeCpa(0, 1)).toBeNull();
    expect(computeCpa(100, 0)).toBeNull();
  });
});
