import { forwardRef, Module } from '@nestjs/common';
import { EventsModule } from '../events/events.module';
import { LeadsFunnelModule } from '../leads-funnel/leads-funnel.module';
import { MetaTrackingModule } from '../meta-tracking/meta-tracking.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { LeadsController } from './leads.controller';
import { LeadsRepository } from './leads.repository';
import { LeadsService } from './leads.service';
import { LeadsWriteService } from './leads-write.service';
import { PgLeadsRepository } from './pg-leads.repository';
import { PgLeadsWriteRepository } from './pg-leads-write.repository';
import { SqliteLeadsRepository } from './sqlite-leads.repository';
import { StaffLeadsWriteGuard } from './guards/staff-leads-write.guard';
import { StaffLeadsViewGuard } from './guards/staff-leads-view.guard';
import { WriteEnabledGuard } from './guards/write-enabled.guard';

@Module({
  imports: [EventsModule, StaffAuthModule, MetaTrackingModule, forwardRef(() => LeadsFunnelModule)],
  controllers: [LeadsController],
  providers: [
    LeadsService,
    LeadsWriteService,
    LeadsRepository,
    SqliteLeadsRepository,
    PgLeadsRepository,
    PgLeadsWriteRepository,
    WriteEnabledGuard,
    StaffLeadsWriteGuard,
    StaffLeadsViewGuard,
  ],
  exports: [LeadsRepository, LeadsWriteService, StaffLeadsViewGuard, StaffLeadsWriteGuard],
})
export class LeadsModule {}
