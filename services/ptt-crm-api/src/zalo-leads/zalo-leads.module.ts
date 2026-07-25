import { Module } from '@nestjs/common';
import { AgencyModule } from '../agency/agency.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { ZaloLeadsController } from './zalo-leads.controller';
import { ZaloLeadsRepository } from './zalo-leads.repository';
import { ZaloLeadsService } from './zalo-leads.service';

@Module({
  imports: [StaffAuthModule, AgencyModule],
  controllers: [ZaloLeadsController],
  providers: [ZaloLeadsService, ZaloLeadsRepository],
  exports: [ZaloLeadsService, ZaloLeadsRepository],
})
export class ZaloLeadsModule {}
