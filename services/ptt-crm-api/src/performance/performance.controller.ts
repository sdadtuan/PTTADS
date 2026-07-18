import {
  Controller,
  ForbiddenException,
  Get,
  Query,
  UseGuards,
} from '@nestjs/common';
import { PortalJwtGuard, PortalUser } from '../portal/portal-jwt.guard';
import { PortalJwtPayload } from '../portal/portal-jwt.util';
import { PerformanceService } from './performance.service';
import { PerformanceListResponse, PerformanceQuery } from './performance.types';

@Controller('api/v1/performance')
export class PerformanceController {
  constructor(private readonly performance: PerformanceService) {}

  @Get()
  @UseGuards(PortalJwtGuard)
  async list(
    @PortalUser() user: PortalJwtPayload,
    @Query() query: PerformanceQuery,
  ): Promise<PerformanceListResponse> {
    const requestedClient = query.client_id?.trim();
    if (requestedClient && requestedClient !== user.client_id) {
      throw new ForbiddenException({ error: 'client_id_mismatch' });
    }
    return this.performance.listForClient(user.client_id, query);
  }
}
