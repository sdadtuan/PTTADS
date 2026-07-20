import { Injectable } from '@nestjs/common';
import { StaffAuthService } from '../staff-auth/staff-auth.service';
import { StaffSectionCap } from '../staff-auth/staff-auth.types';
import { StaffJwtPayload } from '../staff-auth/staff-jwt.util';

export interface CrmBoardModuleCard {
  id: string;
  label: string;
  href: string;
  description: string;
}

const BOARD_MODULES: Array<{
  id: string;
  label: string;
  href: string;
  description: string;
  section: string;
  action?: string;
  altSection?: string;
}> = [
  { id: 'leads', label: 'Leads', href: '/crm/leads', description: 'Pipeline lead', section: 'crm_leads' },
  { id: 'catalog', label: 'Catalog', href: '/crm/catalog', description: 'DV / ngành', section: 'crm_leads' },
  {
    id: 'customers',
    label: 'Customers',
    href: '/crm/customers',
    description: 'Hồ sơ khách hàng',
    section: 'crm_board_customers',
  },
  { id: 'intake', label: 'Lead intake', href: '/crm/intake', description: 'Form gặp KH', section: 'crm_board' },
  {
    id: 'marketing_plan',
    label: 'Marketing plan',
    href: '/crm/marketing-plan',
    description: 'Kế hoạch marketing',
    section: 'crm_board',
  },
  {
    id: 'service_delivery',
    label: 'Service delivery',
    href: '/crm/service-delivery',
    description: 'Triển khai dịch vụ',
    section: 'crm_board',
  },
  { id: 'sop', label: 'SOP', href: '/crm/sop', description: 'Quy trình SOP', section: 'crm_board' },
  {
    id: 'sales',
    label: 'Sales',
    href: '/crm/sales',
    description: 'Kế hoạch bán hàng',
    section: 'crm_sales_overview',
    altSection: 'crm_sales_plans',
  },
  { id: 'proposals', label: 'Proposals', href: '/crm/proposals', description: 'Đề xuất dịch vụ', section: 'crm_board' },
  {
    id: 're_projects',
    label: 'RE projects',
    href: '/crm/re-projects',
    description: 'Dự án BĐS',
    section: 'crm_re_projects',
    altSection: 'crm_re_projects_products',
  },
  {
    id: 'payroll',
    label: 'Payroll',
    href: '/crm/payroll',
    description: 'Chấm công & lương',
    section: 'crm_payroll_salary',
    altSection: 'crm_staff_roster',
  },
  {
    id: 'business_dashboard',
    label: 'Business dashboard',
    href: '/crm/business-dashboard',
    description: 'Tổng quan kinh doanh',
    section: 'crm_business_dashboard',
  },
  {
    id: 'financials',
    label: 'Financials',
    href: '/crm/financials',
    description: 'Báo cáo tài chính',
    section: 'crm_business_dashboard',
  },
  {
    id: 'owner_weekly',
    label: 'Owner weekly',
    href: '/crm/owner-weekly',
    description: 'Dashboard tuần',
    section: 'crm_owner_weekly_dashboard',
  },
  { id: 'staff', label: 'Staff', href: '/crm/staff', description: 'Nhân sự CRM', section: 'crm_staff_roster' },
  { id: 'kpi', label: 'KPI', href: '/crm/kpi', description: 'KPI nhân viên', section: 'crm_kpi_records' },
  {
    id: 'staff_kpi',
    label: 'AM/SP KPI',
    href: '/crm/staff-kpi',
    description: 'KPI AM/SP',
    section: 'crm_staff_kpi_am_sp',
  },
  { id: 'agency', label: 'Agency', href: '/agency', description: 'Agency ops', section: 'crm_agency' },
  { id: 'hub', label: 'Hub map', href: '/crm/hub', description: 'Campaign map', section: 'crm_agency' },
  {
    id: 'meta',
    label: 'Meta hub',
    href: '/meta/facebook-ads',
    description: 'Facebook Ads',
    section: 'crm_facebook_ads',
    altSection: 'crm_agency',
  },
  {
    id: 'seo',
    label: 'SEO hub',
    href: '/seo/hub',
    description: 'SEO / AEO',
    section: 'crm_seo',
    altSection: 'crm_agency',
  },
];

@Injectable()
export class CrmBoardService {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async board(staffUser: StaffJwtPayload) {
    const me = await this.staffAuth.me(staffUser);
    const modules = this.modulesForCaps(me.caps);
    return {
      title: 'CRM Board',
      modules,
      caps_count: me.caps.length,
    };
  }

  private modulesForCaps(caps: StaffSectionCap[]): CrmBoardModuleCard[] {
    const out: CrmBoardModuleCard[] = [];
    const seen = new Set<string>();
    for (const mod of BOARD_MODULES) {
      const allowed =
        this.staffAuth.hasCap(caps, mod.section, mod.action ?? 'view') ||
        (mod.altSection != null && this.staffAuth.hasCap(caps, mod.altSection, 'view'));
      if (!allowed || seen.has(mod.href)) continue;
      seen.add(mod.href);
      out.push({
        id: mod.id,
        label: mod.label,
        href: mod.href,
        description: mod.description,
      });
    }
    return out;
  }
}
