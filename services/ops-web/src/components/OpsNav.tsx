'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import type { StoredStaffUser } from '@/lib/auth';
import { getAccessToken, hasCap } from '@/lib/auth';
import { fetchReviewQueueCount } from '@/lib/api';
import { emailJourneysEnabled, emailModuleEnabled } from '@/lib/email-flags';
import { canViewMetaTracking } from '@/lib/meta/caps';
import { metaTrackingEnabled } from '@/lib/meta/flags';

interface OpsNavProps {
  user: StoredStaffUser | null;
  onLogout: () => void;
  emailPendingApprovals?: number;
  agencyUnread?: number;
}

type NavLink = { href: string; label: string };
type NavSection = { label: string; links: NavLink[] };

const PAGE_TITLES: Record<string, string> = {
  '/': 'Bảng điều khiển',
  '/crm': 'Bảng CSKH',
  '/crm/leads': 'Quản lý Lead',
  '/crm/catalog': 'CRM Catalog',
  '/crm/customers': 'Khách hàng',
  '/crm/intake': 'Lead Intake',
  '/crm/marketing-plan': 'Kế hoạch marketing',
  '/crm/service-delivery': 'Triển khai dịch vụ',
  '/crm/sop': 'Quy trình SOP',
  '/crm/launch-qa': 'Launch QA',
  '/crm/creatives': 'Creative Hub',
  '/crm/campaign-writes': 'Campaign Write',
  '/crm/sales': 'Kinh doanh',
  '/crm/kpi': 'KPI',
  '/crm/staff-kpi': 'KPI AM/SP',
  '/crm/staff': 'Nhân viên',
  '/crm/proposals': 'Đề xuất dịch vụ',
  '/crm/re-projects': 'Dự án BĐS',
  '/crm/payroll': 'Chấm công & lương',
  '/crm/business-dashboard': 'Dashboard kinh doanh',
  '/crm/owner-weekly': 'Báo cáo tuần chủ DN',
  '/crm/financials': 'Tài chính',
  '/agency': 'Agency',
  '/agency/ingest': 'Pipeline ingest',
  '/agency/jobs': 'Pipeline ingest',
  '/agency/notifications': 'Thông báo Agency',
  '/agency/kpi-definitions': 'Định nghĩa KPI',
  '/meta/facebook-ads': 'Meta Ads',
  '/meta/tracking': 'Meta Tracking',
  '/google/google-ads': 'Google Ads',
  '/meta/ads-combined': 'Ads CPL',
  '/meta/migration': 'Meta Migration',
  '/crm/hub': 'Hub · Hợp đồng',
  '/seo/hub': 'SEO/AEO Hub',
  '/seo/clients': 'SEO Clients',
  '/email/hub': 'Email Hub',
  '/email/clients': 'Email Clients',
  '/email/contacts': 'Contacts',
  '/email/consent': 'Consent',
  '/email/suppression': 'Suppression',
  '/email/governance': 'Governance',
  '/email/segments': 'Segments',
  '/email/templates': 'Templates',
  '/email/campaigns': 'Campaigns',
  '/email/journeys': 'Journeys',
  '/email/deliverability': 'Deliverability',
  '/email/reports': 'Reports',
};

function pageTitleFor(pathname: string): string {
  if (pathname.startsWith('/crm/leads/') && pathname !== '/crm/leads') return 'Chi tiết lead';
  if (pathname.startsWith('/crm/customers/') && pathname !== '/crm/customers') return 'Chi tiết khách hàng';
  if (pathname.startsWith('/crm/marketing-plan/') && pathname !== '/crm/marketing-plan') {
    return 'Chi tiết kế hoạch';
  }
  if (pathname.startsWith('/crm/service-delivery/') && pathname !== '/crm/service-delivery') {
    return 'Service lifecycle';
  }
  if (pathname.startsWith('/crm/staff/') && pathname !== '/crm/staff') return 'Workspace nhân viên';
  if (pathname.startsWith('/crm/re-projects/') && pathname !== '/crm/re-projects') return 'Chi tiết dự án BĐS';
  if (pathname.startsWith('/agency/clients/')) return 'Chi tiết client';
  if (pathname.startsWith('/email/templates/') && pathname !== '/email/templates') return 'Template editor';
  if (pathname.startsWith('/email/campaigns/') && pathname.endsWith('/review')) return 'Campaign review';
  if (pathname.startsWith('/email/campaigns/') && pathname !== '/email/campaigns') return 'Campaign detail';
  if (pathname.startsWith('/email/journeys/') && pathname !== '/email/journeys') return 'Journey canvas';
  if (pathname.startsWith('/email/clients/') && pathname !== '/email/clients') return 'Client workspace';
  return PAGE_TITLES[pathname] ?? 'PTT CRM';
}

function navBadge(count: number | undefined): string {
  if (!count || count <= 0) return '';
  return count > 99 ? ' (99+)' : ` (${count})`;
}

function isActive(pathname: string, href: string): boolean {
  return pathname === href || (href !== '/' && pathname.startsWith(`${href}/`));
}

function buildSections(
  user: StoredStaffUser | null,
  emailPendingApprovals?: number,
  agencyUnread?: number,
  reviewQueueCount?: number,
): NavSection[] {
  const sections: NavSection[] = [];

  const overview: NavLink[] = [{ href: '/', label: 'Bảng điều khiển' }];
  if (hasCap(user, 'crm_board', 'view')) {
    overview.push({ href: '/crm', label: 'Bảng CSKH' });
  }
  if (overview.length) sections.push({ label: 'Tổng quan', links: overview });

  const care: NavLink[] = [];
  if (hasCap(user, 'crm_leads', 'view')) {
    care.push({ href: '/crm/leads', label: 'Quản lý Lead' });
    if (hasCap(user, 'crm_leads', 'assign')) {
      care.push({
        href: '/crm/leads/review-queue',
        label: `Phải tra soát (B2)${navBadge(reviewQueueCount)}`,
      });
    }
    care.push({ href: '/crm/catalog', label: 'Catalog' });
  }
  if (hasCap(user, 'crm_board_customers', 'view')) {
    care.push({ href: '/crm/customers', label: 'Khách hàng' });
  }
  if (care.length) sections.push({ label: 'CRM · Chăm sóc KH', links: care });

  const marketing: NavLink[] = [];
  if (hasCap(user, 'crm_agency', 'view')) {
    marketing.push({ href: '/crm/hub', label: 'Hub · Hợp đồng' });
  }
  if (hasCap(user, 'crm_board', 'view')) {
    marketing.push({ href: '/crm/marketing-plan', label: 'Kế hoạch marketing' });
    marketing.push({ href: '/crm/sop', label: 'Quy trình SOP' });
    marketing.push({ href: '/crm/launch-qa', label: 'Launch QA' });
    marketing.push({ href: '/crm/creatives', label: 'Creative Hub' });
    marketing.push({ href: '/crm/campaign-writes', label: 'Campaign Write' });
    marketing.push({ href: '/crm/service-delivery', label: 'Triển khai DV' });
  }
  if (marketing.length) sections.push({ label: 'CRM · Marketing', links: marketing });

  const sales: NavLink[] = [];
  if (hasCap(user, 'crm_sales_overview', 'view') || hasCap(user, 'crm_sales_plans', 'view')) {
    sales.push({ href: '/crm/sales', label: 'Kinh doanh' });
  }
  if (hasCap(user, 'crm_board', 'view')) {
    sales.push({ href: '/crm/proposals', label: 'Đề xuất' });
  }
  if (hasCap(user, 'crm_re_projects', 'view') || hasCap(user, 'crm_re_projects_products', 'view')) {
    sales.push({ href: '/crm/re-projects', label: 'Dự án BĐS' });
  }
  if (sales.length) sections.push({ label: 'CRM · Kinh doanh', links: sales });

  const hr: NavLink[] = [];
  if (hasCap(user, 'crm_staff_roster', 'view')) {
    hr.push({ href: '/crm/staff', label: 'Nhân viên' });
  }
  if (hasCap(user, 'crm_kpi_records', 'view')) {
    hr.push({ href: '/crm/kpi', label: 'KPI' });
  }
  if (hasCap(user, 'crm_staff_kpi_am_sp', 'view')) {
    hr.push({ href: '/crm/staff-kpi', label: 'KPI AM/SP' });
  }
  if (
    hasCap(user, 'crm_payroll_salary', 'view') ||
    hasCap(user, 'crm_payroll_attendance', 'view') ||
    hasCap(user, 'crm_staff_roster', 'view')
  ) {
    hr.push({ href: '/crm/payroll', label: 'Chấm công & lương' });
  }
  if (hr.length) sections.push({ label: 'CRM · Nhân sự', links: hr });

  const finance: NavLink[] = [];
  if (hasCap(user, 'crm_business_dashboard', 'view')) {
    finance.push({ href: '/crm/business-dashboard', label: 'Dashboard KD' });
    finance.push({ href: '/crm/financials', label: 'Tài chính' });
  }
  if (hasCap(user, 'crm_owner_weekly_dashboard', 'view')) {
    finance.push({ href: '/crm/owner-weekly', label: 'BC tuần chủ DN' });
  }
  if (finance.length) sections.push({ label: 'Quản trị', links: finance });

  const agency: NavLink[] = [];
  if (hasCap(user, 'crm_agency', 'view')) {
    agency.push({ href: '/agency', label: 'Agency' });
    agency.push({ href: '/agency/ingest', label: 'Ingest' });
    agency.push({
      href: '/agency/notifications',
      label: `Thông báo${navBadge(agencyUnread)}`,
    });
    agency.push({ href: '/agency/kpi-definitions', label: 'KPI definitions' });
  }
  if (hasCap(user, 'crm_facebook_ads', 'view') || hasCap(user, 'crm_agency', 'view')) {
    agency.push({ href: '/meta/facebook-ads', label: 'Meta Ads' });
    if (metaTrackingEnabled() && canViewMetaTracking(user)) {
      agency.push({ href: '/meta/tracking', label: 'Meta Tracking' });
    }
    agency.push({ href: '/meta/migration', label: 'Meta Migration' });
  }
  if (hasCap(user, 'crm_google_ads', 'view') || hasCap(user, 'crm_agency', 'view')) {
    agency.push({ href: '/google/google-ads', label: 'Google Ads' });
    agency.push({ href: '/meta/ads-combined', label: 'Ads CPL' });
  }
  if (hasCap(user, 'crm_seo', 'view') || hasCap(user, 'crm_agency', 'view')) {
    agency.push({ href: '/seo/hub', label: 'SEO/AEO Hub' });
    agency.push({ href: '/seo/clients', label: 'SEO Clients' });
  }
  if (agency.length) sections.push({ label: 'Agency & Hub', links: agency });

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
    const email: NavLink[] = [
      { href: '/email/hub', label: `Email Hub${navBadge(emailPendingApprovals)}` },
      { href: '/email/clients', label: 'Email Clients' },
      { href: '/email/contacts', label: 'Contacts' },
      { href: '/email/consent', label: 'Consent' },
      { href: '/email/suppression', label: 'Suppression' },
      { href: '/email/governance', label: 'Governance' },
    ];
    if (emailWrite) {
      email.push({ href: '/email/segments', label: 'Segments' });
      email.push({ href: '/email/templates', label: 'Templates' });
      email.push({ href: '/email/campaigns', label: `Campaigns${navBadge(emailPendingApprovals)}` });
    }
    if (emailJourneysEnabled() && emailWrite) {
      email.push({ href: '/email/journeys', label: 'Journeys' });
    }
    if (emailDeliverability) {
      email.push({ href: '/email/deliverability', label: 'Deliverability' });
    }
    if (emailReports) {
      email.push({ href: '/email/reports', label: 'Reports' });
    }
    sections.push({ label: 'Email Marketing', links: email });
  }

  return sections;
}

export function OpsNav({ user, onLogout, emailPendingApprovals, agencyUnread }: OpsNavProps) {
  const pathname = usePathname();
  const [reviewQueueCount, setReviewQueueCount] = useState<number | undefined>();

  useEffect(() => {
    if (!user || !hasCap(user, 'crm_leads', 'assign')) return;
    const token = getAccessToken();
    if (!token) return;
    void fetchReviewQueueCount(token)
      .then((out) => setReviewQueueCount(out.count))
      .catch(() => setReviewQueueCount(undefined));
  }, [user, pathname]);

  const sections = buildSections(user, emailPendingApprovals, agencyUnread, reviewQueueCount);
  const pageTitle = pageTitleFor(pathname);

  return (
    <>
      <aside className="ops-sidebar" aria-label="Điều hướng chính">
        <div className="ops-sidebar-brand">
          <span className="ops-sidebar-brand-mark">PTT</span>
          <div>
            <strong>PTT CRM</strong>
            <span>Staff console</span>
          </div>
        </div>
        <nav className="ops-sidebar-nav">
          {sections.map((section) => (
            <div key={section.label} className="ops-nav-group">
              <p className="ops-nav-group-label">{section.label}</p>
              <div className="ops-nav-group-links">
                {section.links.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={`ops-nav-link${isActive(pathname, link.href) ? ' is-active' : ''}`}
                  >
                    {link.label}
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </nav>
      </aside>

      <header className="ops-topbar">
        <div className="ops-topbar-strip" aria-hidden="true" />
        <div className="ops-topbar-inner">
          <div className="ops-topbar-title">
            <h1>{pageTitle}</h1>
            <p className="muted">
              {user?.display_name ?? user?.email}
              {user?.position_id ? ` · Chức vụ #${user.position_id}` : ''}
            </p>
          </div>
          <button type="button" className="btn btn-topbar-logout" onClick={onLogout}>
            Đăng xuất
          </button>
        </div>
      </header>
    </>
  );
}
