import { Module } from '@nestjs/common';
import { CreativesModule } from '../creatives/creatives.module';
import { LaunchQaModule } from '../launch-qa/launch-qa.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import {
  StaffServiceLifecycleViewGuard,
  StaffServiceLifecycleWriteGuard,
} from '../service-lifecycle/guards/staff-service-lifecycle.guard';
import { CrmCreativesController } from './crm-creatives.controller';
import { CrmCreativesService } from './crm-creatives.service';

@Module({
  imports: [StaffAuthModule, CreativesModule, LaunchQaModule],
  controllers: [CrmCreativesController],
  providers: [CrmCreativesService, StaffServiceLifecycleViewGuard, StaffServiceLifecycleWriteGuard],
})
export class CrmCreativesModule {}
