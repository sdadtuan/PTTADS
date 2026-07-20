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
export class StaffCrmBoardViewGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<
      Request & { staffUser?: StaffJwtPayload; staffAuthVia?: 'internal' | 'jwt' }
    >();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    const allowed =
      this.staffAuth.hasCap(me.caps, 'crm_board', 'view') ||
      this.staffAuth.hasCap(me.caps, 'crm_leads', 'view') ||
      this.staffAuth.hasCap(me.caps, 'crm_board_customers', 'view');
    if (!allowed) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_board' });
    }
    return true;
  }
}
