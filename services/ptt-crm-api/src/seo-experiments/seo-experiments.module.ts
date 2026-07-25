import { Module } from '@nestjs/common';
import { ConfigModule } from '../config/config.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { StaffSeoViewGuard, StaffSeoWriteGuard } from '../seo-admin/guards/staff-seo-view.guard';
import { SeoExperimentsController } from './seo-experiments.controller';
import { SeoExperimentsRepository } from './seo-experiments.repository';
import { SeoExperimentsService } from './seo-experiments.service';

@Module({
  imports: [ConfigModule, StaffAuthModule],
  controllers: [SeoExperimentsController],
  providers: [SeoExperimentsRepository, SeoExperimentsService, StaffSeoViewGuard, StaffSeoWriteGuard],
  exports: [SeoExperimentsService],
})
export class SeoExperimentsModule {}
