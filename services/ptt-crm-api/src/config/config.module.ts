import { Global, Module } from '@nestjs/common';
import { AppConfigService } from './app-config.service';
import { ProdHStubAuditService } from './prod-h.stub-audit.service';

@Global()
@Module({
  providers: [AppConfigService, ProdHStubAuditService],
  exports: [AppConfigService, ProdHStubAuditService],
})
export class ConfigModule {}
