import { Module } from '@nestjs/common';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { CrmBoardController } from './crm-board.controller';
import { CrmBoardService } from './crm-board.service';
import { StaffCrmBoardViewGuard } from './guards/staff-crm-board.guard';

@Module({
  imports: [StaffAuthModule],
  controllers: [CrmBoardController],
  providers: [CrmBoardService, StaffCrmBoardViewGuard],
  exports: [CrmBoardService],
})
export class CrmBoardModule {}
