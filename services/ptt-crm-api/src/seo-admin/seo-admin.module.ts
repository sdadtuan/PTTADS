import { Module } from '@nestjs/common';
import { ConfigModule } from '../config/config.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { SeoAdminController } from './seo-admin.controller';
import { SeoAdminRepository } from './seo-admin.repository';
import { SeoAdminService } from './seo-admin.service';
import { StaffSeoViewGuard } from './guards/staff-seo-view.guard';

@Module({
  imports: [ConfigModule, StaffAuthModule],
  controllers: [SeoAdminController],
  providers: [SeoAdminRepository, SeoAdminService, StaffSeoViewGuard],
  exports: [SeoAdminService],
})
export class SeoAdminModule {}
