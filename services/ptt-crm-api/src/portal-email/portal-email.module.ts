import { Module } from '@nestjs/common';
import { ConfigModule } from '../config/config.module';
import { EmailMarketingModule } from '../email-marketing/email-marketing.module';
import { PortalModule } from '../portal/portal.module';
import { PortalEmailController } from './portal-email.controller';
import { PortalEmailRepository } from './portal-email.repository';
import { PortalEmailService } from './portal-email.service';

@Module({
  imports: [ConfigModule, PortalModule, EmailMarketingModule],
  controllers: [PortalEmailController],
  providers: [PortalEmailRepository, PortalEmailService],
})
export class PortalEmailModule {}
