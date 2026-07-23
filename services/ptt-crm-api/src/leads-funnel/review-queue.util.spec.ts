import {
  isLeadInReviewQueue,
  normalizeB2ContactDeadlineHours,
  reviewQueuePublicState,
} from './review-queue.util';

describe('review-queue.util', () => {
  it('normalizes deadline hours', () => {
    expect(normalizeB2ContactDeadlineHours(24)).toBe(24);
    expect(normalizeB2ContactDeadlineHours(999)).toBe(168);
    expect(normalizeB2ContactDeadlineHours('bad')).toBe(24);
  });

  it('detects active review queue in meta', () => {
    expect(isLeadInReviewQueue({ review_queue: { active: true } })).toBe(true);
    expect(isLeadInReviewQueue({})).toBe(false);
  });

  it('builds public review queue state', () => {
    const state = reviewQueuePublicState(
      {
        review_queue: {
          active: true,
          queued_at: '2026-07-23 10:00:00',
          assigned_at: '2026-07-22 10:00:00',
          deadline_hours: 24,
        },
      },
      '',
      new Date('2026-07-23T12:00:00Z'),
    );
    expect(state.active).toBe(true);
    expect(state.deadline_hours).toBe(24);
  });
});
