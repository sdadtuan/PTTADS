'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import type { StoredStaffUser } from '@/lib/auth';
import { hasCap } from '@/lib/auth';
import { emailJourneysEnabled, emailModuleEnabled } from '@/lib/email-flags';

interface OpsNavProps {
  user: StoredStaffUser | null;
  onLogout: () => void;
  emailPendingApprovals?: number;
}

const PAGE_TITLES: Record<string, string> = {
  '/': 'Dashboard',
  '/crm': 'CRM Board',
  '/crm/leads': 'CRM Leads',
  '/crm/catalog': 'CRM Catalog',
  '/crm/customers': 'CRM Customers',
  '/crm/intake': 'Lead Intake',
  '/crm/marketing-plan': 'Marketing Plan',
  '/crm/service-delivery': 'Service Delivery',
  '/crm/sop': 'SOP',
  '/crm/sales': 'Sales',
  '/crm/kpi': 'KPI',
  '/crm/staff-kpi': 'Staff KPI',
  '/crm/staff': 'Staff',
  '/crm/proposals': 'Proposals',
  '/crm/re-projects': 'RE Projects',
  '/crm/payroll': 'Payroll',
  '/crm/business-dashboard': 'Business Dashboard',
  '/crm/owner-weekly': 'Owner Weekly',
  '/crm/financials': 'Financials',
  '/agency': 'Agency',
  '/meta/facebook-ads': 'Meta Ads Hub',
  '/crm/hub': 'Hub Campaign Map',
  '/seo/hub': 'SEO/AEO Hub',
  '/seo/clients': 'SEO Clients',
  '/email/hub': 'Email Hub',
  '/email/clients': 'Email Clients',
  '/email/contacts': 'Email Contacts',
  '/email/consent': 'Email Consent',
  '/email/suppression': 'Email Suppression',
  '/email/governance': 'Email Governance',
  '/email/segments': 'Email Segments',
  '/email/templates': 'Email Templates',
  '/email/campaigns': 'Email Campaigns',
  '/email/journeys': 'Email Journeys',
  '/email/deliverability': 'Email Deliverability',
  '/email/reports': 'Email Reports',
};

function pageTitleFor(pathname: string): string {
  if (pathname.startsWith('/crm/leads/') && pathname !== '/crm/leads') {
    return 'Lead detail';
  }
  if (pathname.startsWith('/crm/customers/') && pathname !== '/crm/customers') {
    return 'Customer detail';
  }
  if (pathname.startsWith('/crm/marketing-plan/') && pathname !== '/crm/marketing-plan') {
    return 'Marketing plan detail';
  }
  if (pathname.startsWith('/crm/service-delivery/') && pathname !== '/crm/service-delivery') {
    return 'Service lifecycle';
  }
  if (pathname.startsWith('/crm/staff/') && pathname !== '/crm/staff') {
    return 'Staff workspace';
  }
  if (pathname.startsWith('/crm/re-projects/') && pathname !== '/crm/re-projects') {
    return 'RE project detail';
  }
  if (pathname.startsWith('/agency/clients/')) {
    return 'Client detail';
  }
  if (pathname.startsWith('/email/templates/') && pathname !== '/email/templates') {
    return 'Template editor';
  }
  if (pathname.startsWith('/email/campaigns/') && pathname.endsWith('/review')) {
    return 'Campaign review';
  }
  if (pathname.startsWith('/email/campaigns/') && pathname !== '/email/campaigns') {
    return 'Campaign detail';
  }
  if (pathname.startsWith('/email/journeys/') && pathname !== '/email/journeys') {
    return 'Journey canvas';
  }
  if (pathname.startsWith('/email/clients/') && pathname !== '/email/clients') {
    return 'Client workspace';
  }
  return PAGE_TITLES[pathname] ?? 'Ops';
}

function navBadge(count: number | undefined): string {
  if (!count || count <= 0) return '';
  return count > 99 ? ' (99+)' : ` (${count})`;
}

export function OpsNav({ user, onLogout, emailPendingApprovals }: OpsNavProps) {
  const pathname = usePathname();
  const links = [{ href: '/', label: 'Dashboard' }];
  if (hasCap(user, 'crm_board', 'view')) {
    links.push({ href: '/crm', label: 'CRM Board' });
  }
  if (hasCap(user, 'crm_leads', 'view')) {
    links.push({ href: '/crm/leads', label: 'Leads' });
    links.push({ href: '/crm/catalog', label: 'Catalog' });
  }
  if (hasCap(user, 'crm_board_customers', 'view')) {
    links.push({ href: '/crm/customers', label: 'Customers' });
  }
  if (hasCap(user, 'crm_board', 'view')) {
    links.push({ href: '/crm/marketing-plan', label: 'Mkt plan' });
    links.push({ href: '/crm/service-delivery', label: 'Delivery' });
    links.push({ href: '/crm/sop', label: 'SOP' });
  }
  if (hasCap(user, 'crm_sales_overview', 'view') || hasCap(user, 'crm_sales_plans', 'view')) {
    links.push({ href: '/crm/sales', label: 'Sales' });
  }
  if (hasCap(user, 'crm_board', 'view')) {
    links.push({ href: '/crm/proposals', label: 'Proposals' });
  }
  if (hasCap(user, 'crm_re_projects', 'view') || hasCap(user, 'crm_re_projects_products', 'view')) {
    links.push({ href: '/crm/re-projects', label: 'RE' });
  }
  if (
    hasCap(user, 'crm_payroll_salary', 'view') ||
    hasCap(user, 'crm_payroll_attendance', 'view') ||
    hasCap(user, 'crm_staff_roster', 'view')
  ) {
    links.push({ href: '/crm/payroll', label: 'Payroll' });
  }
  if (hasCap(user, 'crm_business_dashboard', 'view')) {
    links.push({ href: '/crm/business-dashboard', label: 'Business' });
    links.push({ href: '/crm/financials', label: 'Financials' });
  }
  if (hasCap(user, 'crm_owner_weekly_dashboard', 'view')) {
    links.push({ href: '/crm/owner-weekly', label: 'Owner weekly' });
  }
  if (hasCap(user, 'crm_staff_roster', 'view')) {
    links.push({ href: '/crm/staff', label: 'Staff' });
  }
  if (hasCap(user, 'crm_kpi_records', 'view')) {
    links.push({ href: '/crm/kpi', label: 'KPI' });
  }
  if (hasCap(user, 'crm_staff_kpi_am_sp', 'view')) {
    links.push({ href: '/crm/staff-kpi', label: 'AM/SP KPI' });
  }
  if (hasCap(user, 'crm_agency', 'view')) {
    links.push({ href: '/agency', label: 'Agency' });
    links.push({ href: '/crm/hub', label: 'Hub map' });
  }
  if (hasCap(user, 'crm_facebook_ads', 'view') || hasCap(user, 'crm_agency', 'view')) {
    links.push({ href: '/meta/facebook-ads', label: 'Meta hub' });
  }
  if (hasCap(user, 'crm_seo', 'view') || hasCap(user, 'crm_agency', 'view')) {
    links.push({ href: '/seo/hub', label: 'SEO hub' });
    links.push({ href: '/seo/clients', label: 'SEO clients' });
  }

  const emailView = hasCap(user, 'crm_email_mkt', 'view') || hasCap(user, 'crm_agency', 'view');
  const emailWrite = hasCap(user, 'crm_email_mkt', 'write') || hasCap(user, 'crm_agency', 'create');
  const emailDeliverability =
    hasCap(user, 'crm_email_mkt', 'deliverability') ||
    hasCap(user, 'crm_email_mkt', 'settings') ||
    hasCap(user, 'crm_agency', 'create');
  const emailReports =
    hasCap(user, 'crm_email_mkt', 'reports') ||
    hasCap(user, 'crm_email_mkt', 'write') ||
    hasCap(user, 'crm_agency', 'view');

  if (emailView && emailModuleEnabled()) {
    links.push({ href: '/email/hub', label: `Email hub${navBadge(emailPendingApprovals)}` });
    links.push({ href: '/email/clients', label: 'Email clients' });
    links.push({ href: '/email/contacts', label: 'Contacts' });
    links.push({ href: '/email/consent', label: 'Consent' });
    links.push({ href: '/email/suppression', label: 'Suppress' });
    links.push({ href: '/email/governance', label: 'Email gov' });
    if (emailWrite) {
      links.push({ href: '/email/segments', label: 'Segments' });
      links.push({ href: '/email/templates', label: 'Templates' });
      links.push({ href: '/email/campaigns', label: `Campaigns${navBadge(emailPendingApprovals)}` });
    }
    if (emailJourneysEnabled() && emailWrite) {
      links.push({ href: '/email/journeys', label: 'Journeys' });
    }
    if (emailDeliverability) {
      links.push({ href: '/email/deliverability', label: 'Deliver' });
    }
    if (emailReports) {
      links.push({ href: '/email/reports', label: 'Reports' });
    }
  }

  const pageTitle = pageTitleFor(pathname);

  return (
    <header
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '1.5rem',
        gap: '1rem',
        flexWrap: 'wrap',
      }}
    >
      <div>
        <p className="badge">PTT Ops</p>
        <h1 style={{ margin: '0.35rem 0 0', fontSize: '1.35rem' }}>{pageTitle}</h1>
        <p className="muted" style={{ margin: '0.25rem 0 0' }}>
          {user?.display_name ?? user?.email}
          {user?.position_id ? ` · position #${user.position_id}` : ''}
        </p>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
        <nav style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={`nav-link${pathname === link.href || pathname.startsWith(`${link.href}/`) ? ' active' : ''}`}
            >
              {link.label}
            </Link>
          ))}
        </nav>
        <button type="button" className="btn btn-secondary" onClick={onLogout}>
          Đăng xuất
        </button>
      </div>
    </header>
  );
}
