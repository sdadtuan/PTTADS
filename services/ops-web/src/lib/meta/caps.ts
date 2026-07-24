import { hasCap, type StoredStaffUser } from '@/lib/auth';
import { metaIntelligenceEnabled, metaTrackingEnabled } from './flags';

export function canViewMetaHub(user: StoredStaffUser | null): boolean {
  if (!user) return false;
  return hasCap(user, 'crm_facebook_ads', 'view') || hasCap(user, 'crm_agency', 'view');
}

export function canConfigureMetaAgency(user: StoredStaffUser | null): boolean {
  if (!user) return false;
  return hasCap(user, 'crm_agency', 'configure');
}

/** Spec alias — agency configure cap for Meta hub writes. */
export const canConfigureMeta = canConfigureMetaAgency;

export function canViewMetaTracking(user: StoredStaffUser | null): boolean {
  if (!user || !metaTrackingEnabled()) return false;
  return hasCap(user, 'crm_facebook_ads', 'view') || hasCap(user, 'crm_agency', 'view');
}

export function canConfigureMetaTracking(user: StoredStaffUser | null): boolean {
  if (!user || !metaTrackingEnabled()) return false;
  return hasCap(user, 'crm_agency', 'configure');
}

export function canApproveMetaCampaignWrite(user: StoredStaffUser | null): boolean {
  if (!user) return false;
  return hasCap(user, 'meta_campaign_write', 'approve');
}

export function canSubmitMetaCampaignWrite(user: StoredStaffUser | null): boolean {
  if (!user) return false;
  return hasCap(user, 'meta_campaign_write', 'view') || hasCap(user, 'crm_board', 'edit');
}

export function canViewMetaIntelligence(user: StoredStaffUser | null): boolean {
  if (!user || !metaIntelligenceEnabled()) return false;
  return hasCap(user, 'crm_facebook_ads', 'view') || hasCap(user, 'crm_agency', 'view');
}
