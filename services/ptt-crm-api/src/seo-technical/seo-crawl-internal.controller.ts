import {
  Body,
  CanActivate,
  Controller,
  ExecutionContext,
  Headers,
  Injectable,
  Param,
  ParseIntPipe,
  Post,
  UnauthorizedException,
  UseGuards,
} from '@nestjs/common';
import { Request } from 'express';
import { SeoTechnicalService } from './seo-technical.service';

@Injectable()
export class SeoCrawlSecretGuard implements CanActivate {
  constructor(private readonly technical: SeoTechnicalService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<Request>();
    const customerId = Number(req.params.customer_id ?? req.params.id);
    if (!Number.isFinite(customerId)) {
      throw new UnauthorizedException({ error: 'invalid_customer_id' });
    }
    const secret = String(req.headers['x-ptt-crawl-secret'] ?? '').trim();
    if (!secret) throw new UnauthorizedException({ error: 'missing_crawl_secret' });
    const ok = await this.technical.verifyCrawlSecret(customerId, secret);
    if (!ok) throw new UnauthorizedException({ error: 'invalid_crawl_secret' });
    return true;
  }
}

@Controller('api/v1/seo/internal/crawl-ingest')
export class SeoCrawlInternalController {
  constructor(private readonly technical: SeoTechnicalService) {}

  @Post(':customer_id')
  @UseGuards(SeoCrawlSecretGuard)
  ingest(
    @Param('customer_id', ParseIntPipe) customerId: number,
    @Body() body: { csv?: string; rows?: Array<Record<string, unknown>> },
    @Headers('x-ptt-crawl-secret') _secret?: string,
  ) {
    void _secret;
    return this.technical.ingestCrawlPayload(customerId, body);
  }
}
