import { Module } from '@nestjs/common';
import { EventsModule } from '../events/events.module';
import { PortalModule } from '../portal/portal.module';
import { CreativesController } from './creatives.controller';
import { CreativesRepository } from './creatives.repository';
import { CreativesService } from './creatives.service';
import { TemporalCreativeService } from './temporal-creative.service';

@Module({
  imports: [PortalModule, EventsModule],
  controllers: [CreativesController],
  providers: [CreativesRepository, CreativesService, TemporalCreativeService],
})
export class CreativesModule {}
