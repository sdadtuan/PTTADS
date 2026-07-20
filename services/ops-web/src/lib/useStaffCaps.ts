import { hasCap, type StoredStaffUser } from '@/lib/auth';
import { emailJourneysEnabled, emailModuleEnabled, emailSendEnabled } from '@/lib/email-flags';

export interface EmailCaps {
  canView: boolean;
  canWrite: boolean;
  canApprove: boolean;
  canDeliverability: boolean;
  canReports: boolean;
  canCompliance: boolean;
  canSettings: boolean;
  moduleEnabled: boolean;
  sendEnabled: boolean;
  journeysEnabled: boolean;
}

export function useEmailCaps(user: StoredStaffUser | null): EmailCaps {
  const agency = hasCap(user, 'crm_agency', 'view');
  const agencyCreate = hasCap(user, 'crm_agency', 'create');
  return {
    canView: hasCap(user, 'crm_email_mkt', 'view') || agency,
    canWrite: hasCap(user, 'crm_email_mkt', 'write') || agencyCreate,
    canApprove: hasCap(user, 'crm_email_mkt', 'approve') || agencyCreate,
    canDeliverability:
      hasCap(user, 'crm_email_mkt', 'deliverability') ||
      hasCap(user, 'crm_email_mkt', 'settings') ||
      agencyCreate,
    canReports:
      hasCap(user, 'crm_email_mkt', 'reports') ||
      hasCap(user, 'crm_email_mkt', 'write') ||
      agency,
    canCompliance: hasCap(user, 'crm_email_mkt', 'compliance') || agencyCreate,
    canSettings: hasCap(user, 'crm_email_mkt', 'settings') || agencyCreate,
    moduleEnabled: emailModuleEnabled(),
    sendEnabled: emailSendEnabled(),
    journeysEnabled: emailJourneysEnabled(),
  };
}
