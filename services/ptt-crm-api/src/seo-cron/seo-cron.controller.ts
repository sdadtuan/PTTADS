import { Controller, Get, Post, UseGuards } from '@nestjs/common';
import { SeoCronSecretGuard } from './seo-cron-secret.guard';
import { SeoCronService } from './seo-cron.service';

@Controller('api/v1/seo/cron')
@UseGuards(SeoCronSecretGuard)
export class SeoCronController {
  constructor(private readonly cron: SeoCronService) {}

  @Get('status')
  status() {
    return this.cron.cronStatus();
  }

  @Post('gate-d')
  gateD() {
    return this.cron.runGateD();
  }

  @Post('gate-e')
  gateE() {
    return this.cron.runGateE();
  }
}
