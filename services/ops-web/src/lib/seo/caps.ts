import { hasCap, type StoredStaffUser } from '@/lib/auth';
import { seoClientWorkspaceEnabled, seoHubEnabled } from './flags';

const SEO_VIEW_SECTIONS = [
  'crm_seo_aeo',
  'crm_seo_aeo_write',
  'crm_seo_aeo_approve',
  'crm_seo_aeo_technical',
  'crm_seo_aeo_settings',
  'crm_seo_aeo_reports',
] as const;

function hasAnySeoSectionView(user: StoredStaffUser): boolean {
  return SEO_VIEW_SECTIONS.some((section) => hasCap(user, section, 'view'));
}

export function canViewSeoHub(user: StoredStaffUser | null): boolean {
  if (!user || !seoHubEnabled()) return false;
  return hasCap(user, 'crm_seo', 'view') || hasCap(user, 'crm_agency', 'view') || hasAnySeoSectionView(user);
}

export function canViewSeoClientWorkspace(user: StoredStaffUser | null): boolean {
  if (!user || !seoClientWorkspaceEnabled()) return false;
  return canViewSeoHub(user);
}

export function canConfigureSeoSettings(user: StoredStaffUser | null): boolean {
  if (!user) return false;
  if (hasCap(user, 'crm_seo_aeo_settings', 'configure') || hasCap(user, 'crm_seo_aeo_settings', 'edit')) {
    return true;
  }
  if (hasCap(user, 'crm_seo_aeo', 'configure') || hasCap(user, 'crm_seo_aeo', 'edit')) {
    return true;
  }
  return hasCap(user, 'crm_agency', 'configure');
}
