import { Module } from '@nestjs/common';
import { ConfigModule } from '../config/config.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { StaffSeoViewGuard, StaffSeoWriteGuard } from '../seo-admin/guards/staff-seo-view.guard';
import { SeoAuthorityController } from './seo-authority.controller';
import { SeoAuthorityRepository } from './seo-authority.repository';
import { SeoAuthorityService } from './seo-authority.service';

@Module({
  imports: [ConfigModule, StaffAuthModule],
  controllers: [SeoAuthorityController],
  providers: [SeoAuthorityRepository, SeoAuthorityService, StaffSeoViewGuard, StaffSeoWriteGuard],
  exports: [SeoAuthorityService],
})
export class SeoAuthorityModule {}
