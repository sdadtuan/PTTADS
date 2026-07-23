import { Module } from '@nestjs/common';
import { EventsModule } from '../events/events.module';
import { LaunchQaModule } from '../launch-qa/launch-qa.module';
import { PortalModule } from '../portal/portal.module';
import { CreativesController } from './creatives.controller';
import { CreativesRepository } from './creatives.repository';
import { CreativesService } from './creatives.service';
import { TemporalCreativeService } from './temporal-creative.service';

@Module({
  imports: [PortalModule, EventsModule, LaunchQaModule],
  controllers: [CreativesController],
  providers: [CreativesRepository, CreativesService, TemporalCreativeService],
  exports: [CreativesRepository, CreativesService],
})
export class CreativesModule {}
