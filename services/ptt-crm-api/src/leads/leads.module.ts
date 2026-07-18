import { Module } from '@nestjs/common';
import { EventsModule } from '../events/events.module';
import { LeadsController } from './leads.controller';
import { LeadsRepository } from './leads.repository';
import { LeadsService } from './leads.service';
import { LeadsWriteService } from './leads-write.service';
import { PgLeadsRepository } from './pg-leads.repository';
import { PgLeadsWriteRepository } from './pg-leads-write.repository';
import { SqliteLeadsRepository } from './sqlite-leads.repository';
import { WriteEnabledGuard } from './guards/write-enabled.guard';

@Module({
  imports: [EventsModule],
  controllers: [LeadsController],
  providers: [
    LeadsService,
    LeadsWriteService,
    LeadsRepository,
    SqliteLeadsRepository,
    PgLeadsRepository,
    PgLeadsWriteRepository,
    WriteEnabledGuard,
  ],
  exports: [LeadsRepository],
})
export class LeadsModule {}
