import {
  CanActivate,
  ExecutionContext,
  ForbiddenException,
  Injectable,
  UnauthorizedException,
} from '@nestjs/common';
import { Request } from 'express';
import { StaffAuthService } from '../../staff-auth/staff-auth.service';
import { StaffJwtPayload } from '../../staff-auth/staff-jwt.util';

@Injectable()
export class StaffMetaAlertsViewGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<
      Request & { staffUser?: StaffJwtPayload; staffAuthVia?: 'internal' | 'jwt' }
    >();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    const meta = this.staffAuth.hasCap(me.caps, 'crm_facebook_ads', 'view');
    const agency = this.staffAuth.hasCap(me.caps, 'crm_agency', 'view');
    if (!meta && !agency) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_facebook_ads' });
    }
    return true;
  }
}

@Injectable()
export class StaffMetaAlertsAckGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<
      Request & { staffUser?: StaffJwtPayload; staffAuthVia?: 'internal' | 'jwt' }
    >();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    const agency = this.staffAuth.hasCap(me.caps, 'crm_agency', 'configure');
    const meta = this.staffAuth.hasCap(me.caps, 'crm_facebook_ads', 'view');
    if (!agency && !meta) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_agency' });
    }
    return true;
  }
}
