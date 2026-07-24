import { hasCap, type StoredStaffUser } from '@/lib/auth';
import { metaTrackingEnabled } from './flags';

export function canViewMetaHub(user: StoredStaffUser | null): boolean {
  if (!user) return false;
  return hasCap(user, 'crm_facebook_ads', 'view') || hasCap(user, 'crm_agency', 'view');
}

export function canConfigureMetaAgency(user: StoredStaffUser | null): boolean {
  if (!user) return false;
  return hasCap(user, 'crm_agency', 'configure');
}

export function canViewMetaTracking(user: StoredStaffUser | null): boolean {
  if (!user || !metaTrackingEnabled()) return false;
  return hasCap(user, 'crm_facebook_ads', 'view') || hasCap(user, 'crm_agency', 'view');
}

export function canConfigureMetaTracking(user: StoredStaffUser | null): boolean {
  if (!user || !metaTrackingEnabled()) return false;
  return hasCap(user, 'crm_agency', 'configure') || hasCap(user, 'crm_facebook_ads', 'view');
}
