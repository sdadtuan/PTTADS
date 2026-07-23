import {
  CanActivate,
  ExecutionContext,
  Injectable,
  NotFoundException,
  ServiceUnavailableException,
} from '@nestjs/common';
import { AppConfigService } from '../../config/app-config.service';

@Injectable()
export class ServiceDeliveryNestGuard implements CanActivate {
  constructor(private readonly config: AppConfigService) {}

  canActivate(_context: ExecutionContext): boolean {
    if (!this.config.crmServiceDeliveryNest) {
      throw new NotFoundException({
        error: 'Wave B5 service delivery routes disabled (PTT_CRM_SERVICE_DELIVERY_NEST=0)',
      });
    }
    if (!this.config.crmLeadsFunnelNest) {
      throw new ServiceUnavailableException({ error: 'PTT_CRM_LEADS_FUNNEL_NEST required' });
    }
    if (!this.config.presalesOnLead) {
      throw new ServiceUnavailableException({ error: 'PTT_PRESALES_ON_LEAD required' });
    }
    return true;
  }
}
