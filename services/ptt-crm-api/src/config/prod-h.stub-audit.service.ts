import { Injectable, Logger, OnModuleInit } from '@nestjs/common';
import { AppConfigService } from './app-config.service';

const PROD_STUB_ENV_FLAGS = [
  'PTT_ZALO_ADS_STUB',
  'PTT_GOOGLE_ADS_STUB',
  'PTT_META_TOKEN_REFRESH_STUB',
  'PTT_ZALO_TOKEN_REFRESH_STUB',
  'PTT_EMAIL_SEND_STUB',
] as const;

function truthyEnv(name: string): boolean {
  return ['1', 'true', 'yes', 'on'].includes((process.env[name] ?? '').trim().toLowerCase());
}

export interface ProdHStubAuditReport {
  ok: boolean;
  violations: string[];
  production_like: boolean;
}

/** PROD-H-STUB — refuse dev stub flags / auth bypass on production-like env. */
@Injectable()
export class ProdHStubAuditService implements OnModuleInit {
  private readonly logger = new Logger(ProdHStubAuditService.name);

  constructor(private readonly config: AppConfigService) {}

  onModuleInit(): void {
    const report = this.audit();
    if (report.ok) {
      if (report.production_like) {
        this.logger.log('PROD-H-STUB audit passed');
      }
      return;
    }
    this.logger.error(`PROD-H-STUB violations: ${report.violations.join('; ')}`);
    if (truthyEnv('PTT_PROD_STUB_AUDIT_FATAL')) {
      throw new Error(`Production stub audit failed: ${report.violations.join(', ')}`);
    }
  }

  audit(): ProdHStubAuditReport {
    const productionLike = this.isProductionLike();
    const violations: string[] = [];

    if (productionLike) {
      for (const flag of PROD_STUB_ENV_FLAGS) {
        if (truthyEnv(flag)) {
          violations.push(`${flag}=1`);
        }
      }
      if (this.config.authDisabled) {
        violations.push('PTT_CRM_API_AUTH_DISABLED=1');
      }
      if (this.config.portalAllowStubUsers) {
        violations.push('portal stub users enabled');
      }
      if (this.config.staffAllowStubUsers) {
        violations.push('staff stub users enabled');
      }
    }

    return { ok: violations.length === 0, violations, production_like: productionLike };
  }

  private isProductionLike(): boolean {
    const nodeEnv = (process.env.NODE_ENV ?? '').trim().toLowerCase();
    return nodeEnv === 'production' || truthyEnv('PTT_PRODUCTION');
  }
}
