import { CanActivate, ExecutionContext, Injectable, NotFoundException } from '@nestjs/common';
import { AppConfigService } from '../../config/app-config.service';

@Injectable()
export class WebhooksEnabledGuard implements CanActivate {
  constructor(private readonly config: AppConfigService) {}

  canActivate(_context: ExecutionContext): boolean {
    if (!this.config.webhooksNestEnabled) {
      throw new NotFoundException({ error: 'webhooks_disabled' });
    }
    return true;
  }
}
