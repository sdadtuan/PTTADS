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

type StaffRequest = Request & {
  staffUser?: StaffJwtPayload;
  staffAuthVia?: 'internal' | 'jwt';
};

@Injectable()
export class StaffPayrollViewGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<StaffRequest>();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    const attendance = this.staffAuth.hasCap(me.caps, 'crm_payroll_attendance', 'view');
    const salary = this.staffAuth.hasCap(me.caps, 'crm_payroll_salary', 'view');
    if (!attendance && !salary) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_payroll_attendance' });
    }
    return true;
  }
}

@Injectable()
export class StaffPayrollSalaryViewGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<StaffRequest>();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    if (!this.staffAuth.hasCap(me.caps, 'crm_payroll_salary', 'view')) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_payroll_salary' });
    }
    return true;
  }
}

@Injectable()
export class StaffPayrollSalaryEditGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<StaffRequest>();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    if (!this.staffAuth.hasCap(me.caps, 'crm_payroll_salary', 'edit')) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_payroll_salary' });
    }
    return true;
  }
}

@Injectable()
export class StaffPayrollSalaryExportGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<StaffRequest>();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    const canExport = this.staffAuth.hasCap(me.caps, 'crm_payroll_salary', 'export');
    const canView = this.staffAuth.hasCap(me.caps, 'crm_payroll_salary', 'view');
    const canEdit = this.staffAuth.hasCap(me.caps, 'crm_payroll_salary', 'edit');
    if (!canExport && !canView && !canEdit) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_payroll_salary' });
    }
    return true;
  }
}
