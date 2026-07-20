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
export class StaffAgencyViewGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<
      Request & { staffUser?: StaffJwtPayload; staffAuthVia?: 'internal' | 'jwt' }
    >();
    if (req.staffAuthVia === 'internal') {
      return true;
    }
    if (!req.staffUser) {
      throw new UnauthorizedException({ error: 'Unauthorized' });
    }
    const me = await this.staffAuth.me(req.staffUser);
    if (!this.staffAuth.hasCap(me.caps, 'crm_agency', 'view')) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_agency' });
    }
    return true;
  }
}

@Injectable()
export class StaffFacebookAdsViewGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<
      Request & { staffUser?: StaffJwtPayload; staffAuthVia?: 'internal' | 'jwt' }
    >();
    if (req.staffAuthVia === 'internal') {
      return true;
    }
    if (!req.staffUser) {
      throw new UnauthorizedException({ error: 'Unauthorized' });
    }
    const me = await this.staffAuth.me(req.staffUser);
    const fb = this.staffAuth.hasCap(me.caps, 'crm_facebook_ads', 'view');
    const agency = this.staffAuth.hasCap(me.caps, 'crm_agency', 'view');
    if (!fb && !agency) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_facebook_ads' });
    }
    return true;
  }
}
