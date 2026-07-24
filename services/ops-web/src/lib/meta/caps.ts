import { hasCap, type StoredStaffUser } from '@/lib/auth';
import { metaAdsOpsEnabled, metaIntelligenceEnabled, metaTrackingEnabled } from './flags';

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

export function canEditMetaCreativeRegistry(user: StoredStaffUser | null): boolean {
  if (!user) return false;
  return hasCap(user, 'crm_facebook_ads', 'edit') || hasCap(user, 'crm_service_lifecycle', 'write');
}

export function canViewMetaAdsOps(user: StoredStaffUser | null): boolean {
  if (!user || !metaAdsOpsEnabled()) return false;
  return (
    hasCap(user, 'crm_facebook_ads', 'view') ||
    hasCap(user, 'crm_agency', 'view') ||
    hasCap(user, 'crm_board', 'edit')
  );
}

export function canSubmitMetaAdsOps(user: StoredStaffUser | null): boolean {
  if (!user || !metaAdsOpsEnabled()) return false;
  return (
    hasCap(user, 'meta_ads_ops', 'submit') ||
    hasCap(user, 'crm_board', 'edit') ||
    hasCap(user, 'crm_facebook_ads', 'edit')
  );
}
