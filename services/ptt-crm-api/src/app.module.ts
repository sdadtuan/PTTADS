import { Module } from '@nestjs/common';
import { AgencyModule } from './agency/agency.module';
import { CasesModule } from './cases/cases.module';
import { CatalogModule } from './catalog/catalog.module';
import { CrmBoardModule } from './crm-board/crm-board.module';
import { CrmLeadsLegacyModule } from './crm-leads-legacy/crm-leads-legacy.module';
import { CrmStaffModule } from './crm-staff/crm-staff.module';
import { KpiModule } from './kpi/kpi.module';
import { SalesModule } from './sales/sales.module';
import { CustomersModule } from './customers/customers.module';
import { IntakeModule } from './intake/intake.module';
import { MarketingPlansModule } from './marketing-plans/marketing-plans.module';
import { ServiceLifecycleModule } from './service-lifecycle/service-lifecycle.module';
import { SvcFinanceModule } from './svc-finance/svc-finance.module';
import { SopModule } from './sop/sop.module';
import { CampaignWritesModule } from './campaign-writes/campaign-writes.module';
import { ConfigModule } from './config/config.module';
import { CreativesModule } from './creatives/creatives.module';
import { FinanceModule } from './finance/finance.module';
import { HealthModule } from './health/health.module';
import { LeadsFunnelModule } from './leads-funnel/leads-funnel.module';
import { LeadsModule } from './leads/leads.module';
import { ObservabilityModule } from './observability/observability.module';
import { PerformanceModule } from './performance/performance.module';
import { PortalEmailModule } from './portal-email/portal-email.module';
import { PortalSeoModule } from './portal-seo/portal-seo.module';
import { PortalModule } from './portal/portal.module';
import { OwnerWeeklyModule } from './owner-weekly/owner-weekly.module';
import { PayrollModule } from './payroll/payroll.module';
import { ProposalsModule } from './proposals/proposals.module';
import { ReProjectsModule } from './re-projects/re-projects.module';
import { EmailMarketingModule } from './email-marketing/email-marketing.module';
import { SeoAdminModule } from './seo-admin/seo-admin.module';
import { StaffAuthModule } from './staff-auth/staff-auth.module';
import { WebhooksModule } from './webhooks/webhooks.module';
import { TemporalModule } from './temporal/temporal.module';
import { WorkflowsModule } from './workflows/workflows.module';

@Module({
  imports: [
    ConfigModule,
    ObservabilityModule,
    HealthModule,
    LeadsModule,
    LeadsFunnelModule,
    CatalogModule,
    CrmLeadsLegacyModule,
    CustomersModule,
    IntakeModule,
    CasesModule,
    SalesModule,
    KpiModule,
    CrmStaffModule,
    ProposalsModule,
    PayrollModule,
    FinanceModule,
    OwnerWeeklyModule,
    ReProjectsModule,
    MarketingPlansModule,
    ServiceLifecycleModule,
    SvcFinanceModule,
    CrmBoardModule,
    SopModule,
    AgencyModule,
    PortalModule,
    StaffAuthModule,
    WebhooksModule,
    PortalSeoModule,
    PortalEmailModule,
    SeoAdminModule,
    EmailMarketingModule,
    PerformanceModule,
    CreativesModule,
    CampaignWritesModule,
    TemporalModule,
    WorkflowsModule,
  ],
})
export class AppModule {}
