import { Body, Controller, Get, HttpCode, HttpStatus, Post, UseGuards } from '@nestjs/common';
import { PortalAuthService, PortalLoginResult } from './portal-auth.service';
import { PortalJwtGuard, PortalUser } from './portal-jwt.guard';
import { PortalJwtPayload } from './portal-jwt.util';

class PortalLoginBody {
  email!: string;
  password!: string;
}

class PortalRefreshBody {
  refresh_token!: string;
}

@Controller('api/v1/portal/auth')
export class PortalAuthController {
  constructor(private readonly auth: PortalAuthService) {}

  @Post('login')
  @HttpCode(HttpStatus.OK)
  async login(@Body() body: PortalLoginBody): Promise<PortalLoginResult> {
    return this.auth.login(body.email ?? '', body.password ?? '');
  }

  @Post('refresh')
  @HttpCode(HttpStatus.OK)
  async refresh(@Body() body: PortalRefreshBody): Promise<PortalLoginResult> {
    return this.auth.refresh(body.refresh_token ?? '');
  }

  @Get('me')
  @UseGuards(PortalJwtGuard)
  me(@PortalUser() user: PortalJwtPayload): {
    id: string;
    email: string;
    client_id: string;
    role: string;
  } {
    return {
      id: user.sub,
      email: user.email,
      client_id: user.client_id,
      role: user.role,
    };
  }
}
