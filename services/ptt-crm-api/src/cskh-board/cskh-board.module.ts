import { Module } from '@nestjs/common';
import { CrmLeadsLegacyModule } from '../crm-leads-legacy/crm-leads-legacy.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { CskhBoardController } from './cskh-board.controller';
import { CskhBoardRepository } from './cskh-board.repository';
import { CskhBoardService } from './cskh-board.service';

@Module({
  imports: [StaffAuthModule, CrmLeadsLegacyModule],
  controllers: [CskhBoardController],
  providers: [CskhBoardRepository, CskhBoardService],
  exports: [CskhBoardService],
})
export class CskhBoardModule {}
