import { hasCap, type StoredStaffUser } from '@/lib/auth';

export function canViewMetaHub(user: StoredStaffUser | null): boolean {
  if (!user) return false;
  return hasCap(user, 'crm_facebook_ads', 'view') || hasCap(user, 'crm_agency', 'view');
}

export function canConfigureMetaAgency(user: StoredStaffUser | null): boolean {
  if (!user) return false;
  return hasCap(user, 'crm_agency', 'configure');
}
