import { Module } from '@nestjs/common';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { CasesController } from './cases.controller';
import { CasesService } from './cases.service';
import { CasesSqliteRepository } from './cases-sqlite.repository';
import { StaffCasesViewGuard, StaffCasesWriteGuard } from './guards/staff-cases.guard';

@Module({
  imports: [StaffAuthModule],
  controllers: [CasesController],
  providers: [
    CasesService,
    CasesSqliteRepository,
    StaffCasesViewGuard,
    StaffCasesWriteGuard,
  ],
  exports: [CasesService],
})
export class CasesModule {}
