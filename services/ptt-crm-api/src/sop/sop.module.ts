import { Module } from '@nestjs/common';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { StaffSopViewGuard, StaffSopWriteGuard } from './guards/staff-sop.guard';
import { SopController } from './sop.controller';
import { SopSqliteRepository } from './sop-sqlite.repository';
import { SopService } from './sop.service';

@Module({
  imports: [StaffAuthModule],
  controllers: [SopController],
  providers: [SopService, SopSqliteRepository, StaffSopViewGuard, StaffSopWriteGuard],
  exports: [SopService],
})
export class SopModule {}
