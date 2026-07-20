import { Module } from '@nestjs/common';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import {
  StaffProposalsViewGuard,
  StaffProposalsWriteGuard,
} from './guards/staff-proposals.guard';
import { ProposalsController } from './proposals.controller';
import { ProposalsSqliteRepository } from './proposals-sqlite.repository';
import { ProposalsService } from './proposals.service';

@Module({
  imports: [StaffAuthModule],
  controllers: [ProposalsController],
  providers: [
    ProposalsService,
    ProposalsSqliteRepository,
    StaffProposalsViewGuard,
    StaffProposalsWriteGuard,
  ],
})
export class ProposalsModule {}
