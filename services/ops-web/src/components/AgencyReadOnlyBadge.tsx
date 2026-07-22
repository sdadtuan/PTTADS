import { hasCap, type StoredStaffUser } from '@/lib/auth';

/** Shown when staff has Agency view but not crm_agency.create (write). */
export function AgencyReadOnlyBadge({ user }: { user: StoredStaffUser | null }) {
  if (!user || hasCap(user, 'crm_agency', 'create')) return null;
  return (
    <span className="agency-readonly-badge" title="Thiếu quyền crm_agency.create">
      Chỉ xem
    </span>
  );
}

export function canAgencyWrite(user: StoredStaffUser | null): boolean {
  return hasCap(user, 'crm_agency', 'create');
}
