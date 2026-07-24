import type { StaffSectionCap } from '../staff-auth/staff-auth.types';

export const MEDIA_BUYER_CAPS: StaffSectionCap[] = [
  { section: 'crm_facebook_ads', action: 'view' },
  { section: 'crm_facebook_ads', action: 'edit' },
  { section: 'meta_campaign_write', action: 'view' },
  { section: 'crm_board', action: 'edit' },
];

export const TRACKING_CAPS: StaffSectionCap[] = [
  { section: 'crm_facebook_ads', action: 'view' },
  { section: 'crm_agency', action: 'configure' },
];

export const META_ADMIN_CAPS: StaffSectionCap[] = [
  ...MEDIA_BUYER_CAPS,
  { section: 'meta_campaign_write', action: 'approve' },
  { section: 'crm_agency', action: 'configure' },
];

export function hasMetaCap(caps: StaffSectionCap[], section: string, action: string): boolean {
  return caps.some((c) => c.section === section && c.action === action);
}

export function canApproveCampaignWrite(caps: StaffSectionCap[]): boolean {
  return hasMetaCap(caps, 'meta_campaign_write', 'approve');
}

export function canConfigureTrackingRules(caps: StaffSectionCap[]): boolean {
  return hasMetaCap(caps, 'crm_agency', 'configure');
}

export function canSubmitCampaignWrite(caps: StaffSectionCap[]): boolean {
  return hasMetaCap(caps, 'meta_campaign_write', 'view') || hasMetaCap(caps, 'crm_board', 'edit');
}
