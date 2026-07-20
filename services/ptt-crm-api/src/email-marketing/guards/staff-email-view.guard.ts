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
export class StaffEmailViewGuard implements CanActivate {
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
    const email = this.staffAuth.hasCap(me.caps, 'crm_email_mkt', 'view');
    const agency = this.staffAuth.hasCap(me.caps, 'crm_agency', 'view');
    if (!email && !agency) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_email_mkt' });
    }
    return true;
  }
}
