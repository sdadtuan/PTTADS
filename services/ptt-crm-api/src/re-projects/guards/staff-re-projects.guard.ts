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

type ReqWithStaff = Request & {
  staffUser?: StaffJwtPayload;
  staffAuthVia?: 'internal' | 'jwt';
};

@Injectable()
export class StaffReProjectsViewGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<ReqWithStaff>();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    const projects = this.staffAuth.hasCap(me.caps, 'crm_re_projects', 'view');
    const products = this.staffAuth.hasCap(me.caps, 'crm_re_projects_products', 'view');
    if (!projects && !products) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_re_projects' });
    }
    return true;
  }
}

@Injectable()
export class StaffReProjectsWriteGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<ReqWithStaff>();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    const canCreate = this.staffAuth.hasCap(me.caps, 'crm_re_projects', 'create');
    const canEdit = this.staffAuth.hasCap(me.caps, 'crm_re_projects', 'edit');
    if (!canCreate && !canEdit) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_re_projects' });
    }
    return true;
  }
}

@Injectable()
export class StaffReProjectsDeleteGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<ReqWithStaff>();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    if (!this.staffAuth.hasCap(me.caps, 'crm_re_projects', 'delete')) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_re_projects' });
    }
    return true;
  }
}

@Injectable()
export class StaffReProjectsUpdateGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<ReqWithStaff & { body?: Record<string, unknown> }>();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    const body = req.body ?? {};
    let section = 'crm_re_projects';
    if ('business_plan' in body) section = 'crm_re_projects_business';
    else if ('marketing_plan' in body) section = 'crm_re_projects_marketing';
    else if ('sales_plan' in body) section = 'crm_re_projects_sales';
    if (!this.staffAuth.hasCap(me.caps, section, 'edit')) {
      throw new ForbiddenException({ error: 'missing_cap', section });
    }
    return true;
  }
}

@Injectable()
export class StaffReProjectsProductsViewGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<ReqWithStaff>();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    const products = this.staffAuth.hasCap(me.caps, 'crm_re_projects_products', 'view');
    const projects = this.staffAuth.hasCap(me.caps, 'crm_re_projects', 'view');
    if (!products && !projects) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_re_projects_products' });
    }
    return true;
  }
}

@Injectable()
export class StaffReProjectsProductsWriteGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<ReqWithStaff>();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    const canCreate = this.staffAuth.hasCap(me.caps, 'crm_re_projects_products', 'create');
    const canEdit = this.staffAuth.hasCap(me.caps, 'crm_re_projects_products', 'edit');
    if (!canCreate && !canEdit) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_re_projects_products' });
    }
    return true;
  }
}

@Injectable()
export class StaffReProjectsProductsDeleteGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<ReqWithStaff>();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    if (!this.staffAuth.hasCap(me.caps, 'crm_re_projects_products', 'delete')) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_re_projects_products' });
    }
    return true;
  }
}

@Injectable()
export class StaffReProjectsBudgetViewGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<ReqWithStaff>();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    if (!this.staffAuth.hasCap(me.caps, 'crm_re_projects_budget', 'view')) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_re_projects_budget' });
    }
    return true;
  }
}

@Injectable()
export class StaffReProjectsBudgetWriteGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<ReqWithStaff>();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    const canCreate = this.staffAuth.hasCap(me.caps, 'crm_re_projects_budget', 'create');
    const canEdit = this.staffAuth.hasCap(me.caps, 'crm_re_projects_budget', 'edit');
    if (!canCreate && !canEdit) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_re_projects_budget' });
    }
    return true;
  }
}

@Injectable()
export class StaffReProjectsBudgetDeleteGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<ReqWithStaff>();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    if (!this.staffAuth.hasCap(me.caps, 'crm_re_projects_budget', 'delete')) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_re_projects_budget' });
    }
    return true;
  }
}

@Injectable()
export class StaffReProjectsBudgetExportGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<ReqWithStaff>();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    const canExport = this.staffAuth.hasCap(me.caps, 'crm_re_projects_budget', 'export');
    const canView = this.staffAuth.hasCap(me.caps, 'crm_re_projects_budget', 'view');
    if (!canExport && !canView) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_re_projects_budget' });
    }
    return true;
  }
}

@Injectable()
export class StaffReProjectsKpiViewGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<ReqWithStaff>();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    if (!this.staffAuth.hasCap(me.caps, 'crm_re_projects_kpi', 'view')) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_re_projects_kpi' });
    }
    return true;
  }
}

@Injectable()
export class StaffReProjectsKpiWriteGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<ReqWithStaff>();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    const canCreate = this.staffAuth.hasCap(me.caps, 'crm_re_projects_kpi', 'create');
    const canEdit = this.staffAuth.hasCap(me.caps, 'crm_re_projects_kpi', 'edit');
    if (!canCreate && !canEdit) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_re_projects_kpi' });
    }
    return true;
  }
}

@Injectable()
export class StaffReProjectsKpiDeleteGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<ReqWithStaff>();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    if (!this.staffAuth.hasCap(me.caps, 'crm_re_projects_kpi', 'delete')) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_re_projects_kpi' });
    }
    return true;
  }
}

@Injectable()
export class StaffReProjectsRisksViewGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<ReqWithStaff>();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    if (!this.staffAuth.hasCap(me.caps, 'crm_re_projects_risks', 'view')) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_re_projects_risks' });
    }
    return true;
  }
}

@Injectable()
export class StaffReProjectsRisksWriteGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<ReqWithStaff>();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    const canCreate = this.staffAuth.hasCap(me.caps, 'crm_re_projects_risks', 'create');
    const canEdit = this.staffAuth.hasCap(me.caps, 'crm_re_projects_risks', 'edit');
    if (!canCreate && !canEdit) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_re_projects_risks' });
    }
    return true;
  }
}

@Injectable()
export class StaffReProjectsRisksDeleteGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<ReqWithStaff>();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    if (!this.staffAuth.hasCap(me.caps, 'crm_re_projects_risks', 'delete')) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_re_projects_risks' });
    }
    return true;
  }
}

@Injectable()
export class StaffReProjectsExportGuard implements CanActivate {
  constructor(private readonly staffAuth: StaffAuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<ReqWithStaff>();
    if (req.staffAuthVia === 'internal') return true;
    if (!req.staffUser) throw new UnauthorizedException({ error: 'Unauthorized' });
    const me = await this.staffAuth.me(req.staffUser);
    const canExport = this.staffAuth.hasCap(me.caps, 'crm_re_projects', 'export');
    const canView = this.staffAuth.hasCap(me.caps, 'crm_re_projects', 'view');
    if (!canExport && !canView) {
      throw new ForbiddenException({ error: 'missing_cap', section: 'crm_re_projects' });
    }
    return true;
  }
}
