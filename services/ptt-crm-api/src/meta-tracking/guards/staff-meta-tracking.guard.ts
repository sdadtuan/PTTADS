import {
  CanActivate,
  ExecutionContext,
  ForbiddenException,
  Injectable,
  ServiceUnavailableException,
  UnauthorizedException,
} from '@nestjs/common';
import { Request } from 'express';
import { StaffAuthService } from '../../staff-auth/staff-auth.service';
import { StaffJwtPayload } from '../../staff-auth/staff-jwt.util';

function isMetaTrackingEnabled(): boolean {
  return ['1', 'true', 'yes', 'on'].includes(
    (process.env.PTT_META_TRACKING_ENABLED ?? '0').trim().toLowerCase(),
  );
}

@Injectable()
export class StaffMetaTrackingEnabledGuard implements CanActivate {
  canActivate(): boolean {
    if (!isMetaTrackingEnabled()) {
      throw new ServiceUnavailableException({ ok: false, error: 'meta_tracking_disabled' });
    }
    return true;
  }
}

@Injectable()
export class StaffMetaTrackingViewGuard implements CanActivate {
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
export class StaffMetaTrackingConfigureGuard implements CanActivate {
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
