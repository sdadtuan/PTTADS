import { Module } from '@nestjs/common';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { StaffIntakeViewGuard, StaffIntakeWriteGuard } from './guards/staff-intake.guard';
import { IntakeController } from './intake.controller';
import { IntakeService } from './intake.service';
import { IntakeSqliteRepository } from './intake-sqlite.repository';

@Module({
  imports: [StaffAuthModule],
  controllers: [IntakeController],
  providers: [
    IntakeService,
    IntakeSqliteRepository,
    StaffIntakeViewGuard,
    StaffIntakeWriteGuard,
  ],
  exports: [IntakeService],
})
export class IntakeModule {}
