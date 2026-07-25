import { Module } from '@nestjs/common';
import { ConfigModule } from '../config/config.module';
import { SeoAeoModule } from '../seo-aeo/seo-aeo.module';
import { SeoRanksModule } from '../seo-ranks/seo-ranks.module';
import { SeoReportsModule } from '../seo-reports/seo-reports.module';
import { SeoTechnicalModule } from '../seo-technical/seo-technical.module';
import { SeoCronController } from './seo-cron.controller';
import { SeoCronRepository } from './seo-cron.repository';
import { SeoCronService } from './seo-cron.service';
import { SeoCronSecretGuard } from './seo-cron-secret.guard';

@Module({
  imports: [ConfigModule, SeoTechnicalModule, SeoAeoModule, SeoRanksModule, SeoReportsModule],
  controllers: [SeoCronController],
  providers: [SeoCronRepository, SeoCronService, SeoCronSecretGuard],
  exports: [SeoCronService, SeoCronRepository],
})
export class SeoCronModule {}
