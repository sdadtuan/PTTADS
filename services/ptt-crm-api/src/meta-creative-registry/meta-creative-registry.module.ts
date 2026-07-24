import { Module } from '@nestjs/common';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import {
  StaffMetaCreativeRegistryEditGuard,
  StaffMetaCreativeRegistryViewGuard,
} from './guards/staff-meta-creative-registry.guard';
import { MetaCreativeRegistryController } from './meta-creative-registry.controller';
import { MetaCreativeRegistryRepository } from './meta-creative-registry.repository';
import { MetaCreativeRegistryService } from './meta-creative-registry.service';

@Module({
  imports: [StaffAuthModule],
  controllers: [MetaCreativeRegistryController],
  providers: [
    MetaCreativeRegistryRepository,
    MetaCreativeRegistryService,
    StaffMetaCreativeRegistryViewGuard,
    StaffMetaCreativeRegistryEditGuard,
  ],
  exports: [MetaCreativeRegistryRepository, MetaCreativeRegistryService],
})
export class MetaCreativeRegistryModule {}
