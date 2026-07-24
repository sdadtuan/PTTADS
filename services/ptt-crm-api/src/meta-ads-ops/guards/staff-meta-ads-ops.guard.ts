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
export class StaffMetaAdsOpsViewGuard implements CanActivate {
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
    const board = this.staffAuth.hasCap(me.caps, 'crm_board', 'edit');
    if (!meta && !agency && !board) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'meta_ads_ops' });
    }
    return true;
  }
}

@Injectable()
export class StaffMetaAdsOpsSubmitGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<
      Request & { staffUser?: StaffJwtPayload; staffAuthVia?: 'internal' | 'jwt' }
    >();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    const submit = this.staffAuth.hasCap(me.caps, 'meta_ads_ops', 'submit');
    const board = this.staffAuth.hasCap(me.caps, 'crm_board', 'edit');
    const metaEdit = this.staffAuth.hasCap(me.caps, 'crm_facebook_ads', 'edit');
    if (!submit && !board && !metaEdit) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'meta_ads_ops' });
    }
    return true;
  }
}
