import {
  Controller,
  Get,
  HttpCode,
  HttpStatus,
  Param,
  Patch,
  Query,
  UseGuards,
} from '@nestjs/common';
import { PortalJwtGuard, PortalUser } from './portal-jwt.guard';
import { PortalJwtPayload } from './portal-jwt.util';
import { PortalNotificationService } from './portal-notification.service';
import {
  PortalNotificationListResponse,
  PortalNotificationSummaryResponse,
} from './portal-notification.types';

@Controller('api/v1/portal/notifications')
export class PortalNotificationController {
  constructor(private readonly notifications: PortalNotificationService) {}

  @Get()
  @UseGuards(PortalJwtGuard)
  list(
    @PortalUser() user: PortalJwtPayload,
    @Query('unread_only') unreadOnly?: string,
    @Query('limit') limit?: string,
  ): Promise<PortalNotificationListResponse> {
    return this.notifications.list(user, {
      unreadOnly: unreadOnly === '1' || unreadOnly === 'true',
      limit: limit ? Number(limit) : undefined,
    });
  }

  @Get('summary')
  @UseGuards(PortalJwtGuard)
  summary(@PortalUser() user: PortalJwtPayload): Promise<PortalNotificationSummaryResponse> {
    return this.notifications.summary(user);
  }

  @Patch('read-all')
  @HttpCode(HttpStatus.OK)
  @UseGuards(PortalJwtGuard)
  markAllRead(@PortalUser() user: PortalJwtPayload) {
    return this.notifications.markAllRead(user);
  }

  @Patch(':id/read')
  @HttpCode(HttpStatus.OK)
  @UseGuards(PortalJwtGuard)
  markRead(@PortalUser() user: PortalJwtPayload, @Param('id') id: string) {
    return this.notifications.markRead(user, id);
  }
}
