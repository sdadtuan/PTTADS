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
import { MetaTrackingModule } from './meta-tracking/meta-tracking.module';
import { MetaAlertsModule } from './meta-alerts/meta-alerts.module';
import { MetaIntelligenceModule } from './meta-intelligence/meta-intelligence.module';
import { MetaCreativeRegistryModule } from './meta-creative-registry/meta-creative-registry.module';
import { MetaComplianceModule } from './meta-compliance/meta-compliance.module';
import { MetaAdsOpsModule } from './meta-ads-ops/meta-ads-ops.module';
import { MetricsModule } from './metrics/metrics.module';
import { MarketingPlansModule } from './marketing-plans/marketing-plans.module';
import { ServiceLifecycleModule } from './service-lifecycle/service-lifecycle.module';
import { SvcFinanceModule } from './svc-finance/svc-finance.module';
import { SopModule } from './sop/sop.module';
import { CampaignWritesModule } from './campaign-writes/campaign-writes.module';
import { ConfigModule } from './config/config.module';
import { CreativesModule } from './creatives/creatives.module';
import { FinanceModule } from './finance/finance.module';
import { HealthModule } from './health/health.module';
import { LaunchQaModule } from './launch-qa/launch-qa.module';
import { CrmCreativesModule } from './crm-creatives/crm-creatives.module';
import { CrmCampaignWritesModule } from './crm-campaign-writes/crm-campaign-writes.module';
import { LeadsFunnelModule } from './leads-funnel/leads-funnel.module';
import { LeadsContractModule } from './leads-contract/leads-contract.module';
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
import { SeoBiModule } from './seo-bi/seo-bi.module';
import { SeoCmsModule } from './seo-cms/seo-cms.module';
import { SeoCronModule } from './seo-cron/seo-cron.module';
import { SeoAeoModule } from './seo-aeo/seo-aeo.module';
import { SeoAuthorityModule } from './seo-authority/seo-authority.module';
import { SeoAutomationsModule } from './seo-automations/seo-automations.module';
import { SeoContentModule } from './seo-content/seo-content.module';
import { SeoExperimentsModule } from './seo-experiments/seo-experiments.module';
import { SeoFreshnessModule } from './seo-freshness/seo-freshness.module';
import { SeoGovernanceModule } from './seo-governance/seo-governance.module';
import { SeoRanksModule } from './seo-ranks/seo-ranks.module';
import { SeoReportsModule } from './seo-reports/seo-reports.module';
import { SeoStrategyModule } from './seo-strategy/seo-strategy.module';
import { SeoTechnicalModule } from './seo-technical/seo-technical.module';
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
    LeadsContractModule,
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
    LaunchQaModule,
    CrmCreativesModule,
    CrmCampaignWritesModule,
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
    SeoContentModule,
    SeoTechnicalModule,
    SeoReportsModule,
    SeoGovernanceModule,
    SeoStrategyModule,
    SeoAeoModule,
    SeoAuthorityModule,
    SeoRanksModule,
    SeoAutomationsModule,
    SeoFreshnessModule,
    SeoExperimentsModule,
    SeoBiModule,
    SeoCronModule,
    SeoCmsModule,
    EmailMarketingModule,
    PerformanceModule,
    MetaTrackingModule,
    MetaAlertsModule,
    MetaIntelligenceModule,
    MetaCreativeRegistryModule,
    MetaComplianceModule,
    MetaAdsOpsModule,
    MetricsModule,
    CreativesModule,
    CampaignWritesModule,
    TemporalModule,
    WorkflowsModule,
  ],
})
export class AppModule {}
