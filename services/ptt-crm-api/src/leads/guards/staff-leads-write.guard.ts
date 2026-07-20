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
export class StaffLeadsWriteGuard implements CanActivate {
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
    const canEdit = this.staffAuth.hasCap(me.caps, 'crm_leads', 'edit');
    const canAssign = this.staffAuth.hasCap(me.caps, 'crm_leads', 'assign');
    if (!canEdit && !canAssign) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_leads' });
    }
    return true;
  }
}
