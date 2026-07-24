import {
  canApproveCampaignWrite,
  canConfigureTrackingRules,
  canSubmitCampaignWrite,
  MEDIA_BUYER_CAPS,
  META_ADMIN_CAPS,
  TRACKING_CAPS,
} from './meta-rbac.util';

describe('meta-rbac.util', () => {
  it('buyer cannot approve campaign write', () => {
    expect(canApproveCampaignWrite(MEDIA_BUYER_CAPS)).toBe(false);
    expect(canSubmitCampaignWrite(MEDIA_BUYER_CAPS)).toBe(true);
  });

  it('tracking can configure rules but not approve writes', () => {
    expect(canConfigureTrackingRules(TRACKING_CAPS)).toBe(true);
    expect(canApproveCampaignWrite(TRACKING_CAPS)).toBe(false);
  });

  it('admin meta caps include approve + configure', () => {
    expect(canApproveCampaignWrite(META_ADMIN_CAPS)).toBe(true);
    expect(canConfigureTrackingRules(META_ADMIN_CAPS)).toBe(true);
  });
});
