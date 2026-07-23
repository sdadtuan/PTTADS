import { Module } from '@nestjs/common';
import { EventsModule } from '../events/events.module';
import { CampaignWritesController } from './campaign-writes.controller';
import { CampaignWritesRepository } from './campaign-writes.repository';
import { CampaignWritesService } from './campaign-writes.service';
import { TemporalCampaignWriteService } from './temporal-campaign-write.service';

@Module({
  imports: [EventsModule],
  controllers: [CampaignWritesController],
  providers: [CampaignWritesRepository, CampaignWritesService, TemporalCampaignWriteService],
  exports: [CampaignWritesRepository, CampaignWritesService],
})
export class CampaignWritesModule {}
