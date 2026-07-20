import { Module } from '@nestjs/common';
import { ConfigModule } from '../config/config.module';
import { PortalModule } from '../portal/portal.module';
import { PortalSeoController } from './portal-seo.controller';
import { PortalSeoRepository } from './portal-seo.repository';
import { PortalSeoService } from './portal-seo.service';

@Module({
  imports: [ConfigModule, PortalModule],
  controllers: [PortalSeoController],
  providers: [PortalSeoRepository, PortalSeoService],
})
export class PortalSeoModule {}
