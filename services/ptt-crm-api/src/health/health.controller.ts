import { Controller, Get } from '@nestjs/common';
import { AppConfigService } from '../config/app-config.service';

@Controller('health')
export class HealthController {
  constructor(private readonly config: AppConfigService) {}

  @Get()
  getHealth(): {
    ok: boolean;
    service: string;
    leads_read_source: string;
    leads_write_enabled: boolean;
    leads_create_id_mode: string;
    portal_auth_stub_users: number;
    sqlite: boolean;
    postgres: boolean;
  } {
    return {
      ok: true,
      service: 'ptt-crm-api',
      leads_read_source: this.config.leadsReadSource,
      leads_write_enabled: this.config.leadsWriteEnabled,
      leads_create_id_mode: this.config.leadsCreateIdMode,
      portal_auth_stub_users: this.config.portalStubUsers.length,
      sqlite: this.config.sqliteAvailable(),
      postgres: Boolean(this.config.databaseUrl),
    };
  }
}
