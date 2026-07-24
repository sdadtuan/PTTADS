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
export class StaffMetaCreativeRegistryViewGuard implements CanActivate {
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
    const lifecycle = this.staffAuth.hasCap(me.caps, 'crm_service_lifecycle', 'view');
    if (!meta && !agency && !lifecycle) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_facebook_ads' });
    }
    return true;
  }
}

@Injectable()
export class StaffMetaCreativeRegistryEditGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<
      Request & { staffUser?: StaffJwtPayload; staffAuthVia?: 'internal' | 'jwt' }
    >();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    const metaEdit = this.staffAuth.hasCap(me.caps, 'crm_facebook_ads', 'edit');
    const lifecycleWrite = this.staffAuth.hasCap(me.caps, 'crm_service_lifecycle', 'write');
    if (!metaEdit && !lifecycleWrite) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_facebook_ads', action: 'edit' });
    }
    return true;
  }
}
