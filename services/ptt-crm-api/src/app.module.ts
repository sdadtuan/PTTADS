import { Module } from '@nestjs/common';
import { CampaignWritesModule } from './campaign-writes/campaign-writes.module';
import { ConfigModule } from './config/config.module';
import { CreativesModule } from './creatives/creatives.module';
import { HealthModule } from './health/health.module';
import { LeadsModule } from './leads/leads.module';
import { ObservabilityModule } from './observability/observability.module';
import { PerformanceModule } from './performance/performance.module';
import { PortalModule } from './portal/portal.module';
import { TemporalModule } from './temporal/temporal.module';
import { WorkflowsModule } from './workflows/workflows.module';

@Module({
  imports: [
    ConfigModule,
    ObservabilityModule,
    HealthModule,
    LeadsModule,
    PortalModule,
    PerformanceModule,
    CreativesModule,
    CampaignWritesModule,
    TemporalModule,
    WorkflowsModule,
  ],
})
export class AppModule {}
