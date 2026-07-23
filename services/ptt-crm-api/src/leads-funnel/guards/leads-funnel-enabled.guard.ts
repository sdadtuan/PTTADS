import {
  CanActivate,
  ExecutionContext,
  Injectable,
  NotFoundException,
  ServiceUnavailableException,
} from '@nestjs/common';
import { AppConfigService } from '../../config/app-config.service';

@Injectable()
export class LeadsFunnelEnabledGuard implements CanActivate {
  constructor(private readonly config: AppConfigService) {}

  canActivate(_context: ExecutionContext): boolean {
    if (!this.config.crmLeadsFunnelNest) {
      throw new NotFoundException({ error: 'Wave B4 funnel routes disabled (PTT_CRM_LEADS_FUNNEL_NEST=0)' });
    }
    return true;
  }
}

@Injectable()
export class PresalesOnLeadGuard implements CanActivate {
  constructor(private readonly config: AppConfigService) {}

  canActivate(_context: ExecutionContext): boolean {
    if (!this.config.presalesOnLead) {
      throw new ServiceUnavailableException({ error: 'PTT_PRESALES_ON_LEAD is disabled' });
    }
    return true;
  }
}
