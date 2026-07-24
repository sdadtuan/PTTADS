import { MetaTrackingRepository } from './meta-tracking.repository';
import {
  evaluateMetaLaunchQaItems,
  isMetaLaunchQaEnabled,
  isMetaLaunchQaStrict,
  mergeMetaLaunchQaChecklist,
} from './launch-qa-meta.util';

describe('launch-qa-meta.util', () => {
  describe('mergeMetaLaunchQaChecklist', () => {
    const prev = process.env.PTT_META_TRACKING_ENABLED;

    afterEach(() => {
      process.env.PTT_META_TRACKING_ENABLED = prev;
    });

    it('adds meta items when tracking enabled', () => {
      process.env.PTT_META_TRACKING_ENABLED = '1';
      const merged = mergeMetaLaunchQaChecklist({ pixel_verified: { label: 'x', completed: false } });
      expect(merged.meta_pixel_configured).toBeDefined();
      expect(merged.meta_capi_test_ok).toBeDefined();
    });

    it('skips meta items when tracking disabled', () => {
      process.env.PTT_META_TRACKING_ENABLED = '0';
      const merged = mergeMetaLaunchQaChecklist({ pixel_verified: { label: 'x', completed: false } });
      expect(merged.meta_pixel_configured).toBeUndefined();
    });
  });

  describe('evaluateMetaLaunchQaItems', () => {
    const repo = {
      listTrackingAccounts: jest.fn(),
      computeUnmappedSpendPct: jest.fn(),
      getLastCapiSentAt: jest.fn(),
      getChannelAccountMetaJson: jest.fn(),
    } as unknown as MetaTrackingRepository;

    beforeEach(() => {
      jest.resetAllMocks();
      process.env.PTT_META_TRACKING_ENABLED = '1';
      process.env.PTT_LAUNCH_QA_META_STRICT = '0';
      (repo.listTrackingAccounts as jest.Mock).mockResolvedValue([
        {
          client_id: 'c1',
          channel_account_id: 'a1',
          pixel_id: 'px123',
          page_id: null,
          capi_enabled: true,
          last_sent_at: null,
          pixel_test_ok: null,
          client_code: 'T1',
          client_name: 'Test',
        },
      ]);
      (repo.computeUnmappedSpendPct as jest.Mock).mockResolvedValue({
        total_spend: 1000,
        unmapped_spend: 100,
        unmapped_spend_pct: 10,
      });
      (repo.getLastCapiSentAt as jest.Mock).mockResolvedValue(null);
      (repo.getChannelAccountMetaJson as jest.Mock).mockResolvedValue({
        pixel_test_ok_at: new Date().toISOString(),
      });
    });

    it('passes pixel, test, hub map when data ok', async () => {
      const items = await evaluateMetaLaunchQaItems(repo, 'c1');
      const byKey = Object.fromEntries(items.map((i) => [i.key, i.passed]));
      expect(byKey.meta_pixel_configured).toBe(true);
      expect(byKey.meta_capi_test_ok).toBe(true);
      expect(byKey.meta_hub_map_coverage).toBe(true);
      expect(byKey.meta_capi_recent_sent).toBe(true);
    });

    it('fails pixel when missing', async () => {
      (repo.listTrackingAccounts as jest.Mock).mockResolvedValue([
        {
          client_id: 'c1',
          channel_account_id: 'a1',
          pixel_id: null,
          page_id: null,
          capi_enabled: false,
          last_sent_at: null,
          pixel_test_ok: null,
          client_code: 'T1',
          client_name: 'Test',
        },
      ]);
      const items = await evaluateMetaLaunchQaItems(repo, 'c1');
      expect(items.find((i) => i.key === 'meta_pixel_configured')?.passed).toBe(false);
    });

    it('requires recent sent when strict', async () => {
      process.env.PTT_LAUNCH_QA_META_STRICT = '1';
      const items = await evaluateMetaLaunchQaItems(repo, 'c1');
      expect(items.find((i) => i.key === 'meta_capi_recent_sent')?.passed).toBe(false);
    });
  });

  it('isMetaLaunchQaEnabled reads env', () => {
    process.env.PTT_META_TRACKING_ENABLED = '1';
    expect(isMetaLaunchQaEnabled()).toBe(true);
    process.env.PTT_META_TRACKING_ENABLED = '0';
    expect(isMetaLaunchQaEnabled()).toBe(false);
  });

  it('isMetaLaunchQaStrict reads env', () => {
    process.env.PTT_LAUNCH_QA_META_STRICT = '1';
    expect(isMetaLaunchQaStrict()).toBe(true);
  });
});
