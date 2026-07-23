import { Body, Controller, Get, Patch, UseGuards } from '@nestjs/common';
import { PortalJwtGuard, PortalUser } from './portal-jwt.guard';
import { PortalJwtPayload } from './portal-jwt.util';
import { PortalSettingsService, PortalSettingsResponse } from './portal-settings.service';

class PatchPortalSettingsBody {
  display_name?: string;
  logo_url?: string;
  am_contact_name?: string;
  am_contact_email?: string;
  accent_color?: string;
}

@Controller('api/v1/portal/settings')
export class PortalSettingsController {
  constructor(private readonly settings: PortalSettingsService) {}

  @Get()
  @UseGuards(PortalJwtGuard)
  get(@PortalUser() user: PortalJwtPayload): Promise<PortalSettingsResponse> {
    return this.settings.getForUser(user);
  }

  @Patch()
  @UseGuards(PortalJwtGuard)
  patch(
    @PortalUser() user: PortalJwtPayload,
    @Body() body: PatchPortalSettingsBody,
  ): Promise<PortalSettingsResponse> {
    return this.settings.patchForUser(user, body ?? {});
  }
}
