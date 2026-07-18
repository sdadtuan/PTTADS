import { CanActivate, Injectable, NotFoundException } from '@nestjs/common';
import { AppConfigService } from '../../config/app-config.service';

/** Hide write routes when PTT_LEADS_WRITE_ENABLED=0 (production default). */
@Injectable()
export class WriteEnabledGuard implements CanActivate {
  constructor(private readonly config: AppConfigService) {}

  canActivate(): boolean {
    if (!this.config.leadsWriteEnabled) {
      throw new NotFoundException({ error: 'Not found' });
    }
    return true;
  }
}
