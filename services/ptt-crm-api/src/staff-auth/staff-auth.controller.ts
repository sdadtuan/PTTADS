import { Body, Controller, Get, HttpCode, HttpStatus, Post, UseGuards } from '@nestjs/common';
import { StaffAuthService } from './staff-auth.service';
import { StaffLoginResult, StaffMeResponse } from './staff-auth.types';
import { StaffJwtGuard, StaffUser } from './staff-jwt.guard';
import { StaffJwtPayload } from './staff-jwt.util';

class StaffLoginBody {
  email!: string;
  password!: string;
}

class StaffRefreshBody {
  refresh_token!: string;
}

@Controller('api/v1/staff/auth')
export class StaffAuthController {
  constructor(private readonly auth: StaffAuthService) {}

  @Post('login')
  @HttpCode(HttpStatus.OK)
  async login(@Body() body: StaffLoginBody): Promise<StaffLoginResult> {
    return this.auth.login(body.email ?? '', body.password ?? '');
  }

  @Post('refresh')
  @HttpCode(HttpStatus.OK)
  refresh(@Body() body: StaffRefreshBody): StaffLoginResult {
    return this.auth.refresh(body.refresh_token ?? '');
  }

  @Get('me')
  @UseGuards(StaffJwtGuard)
  async me(@StaffUser() user: StaffJwtPayload): Promise<StaffMeResponse> {
    return this.auth.me(user);
  }
}
