import { hasCap, type StoredStaffUser } from '@/lib/auth';
import { emailGateAEnabled, emailModuleEnabled } from '@/lib/email-flags';

export function canViewEmailGateA(user: StoredStaffUser | null): boolean {
  if (!user || !emailModuleEnabled() || !emailGateAEnabled()) return false;
  return (
    hasCap(user, 'crm_email_mkt', 'settings') ||
    hasCap(user, 'crm_email_mkt', 'view') ||
    hasCap(user, 'crm_agency', 'view')
  );
}
