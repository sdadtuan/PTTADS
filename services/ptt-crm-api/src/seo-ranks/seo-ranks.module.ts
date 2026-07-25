import { Module } from '@nestjs/common';
import { ConfigModule } from '../config/config.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { StaffSeoViewGuard, StaffSeoWriteGuard } from '../seo-admin/guards/staff-seo-view.guard';
import { SeoRanksController } from './seo-ranks.controller';
import { SeoRanksRepository } from './seo-ranks.repository';
import { SeoRanksService } from './seo-ranks.service';

@Module({
  imports: [ConfigModule, StaffAuthModule],
  controllers: [SeoRanksController],
  providers: [SeoRanksRepository, SeoRanksService, StaffSeoViewGuard, StaffSeoWriteGuard],
  exports: [SeoRanksService, SeoRanksRepository],
})
export class SeoRanksModule {}
