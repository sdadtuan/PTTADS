import { Body, Controller, Get, HttpCode, HttpStatus, Post, Query, UseGuards } from '@nestjs/common';
import { PortalAuthService, PortalLoginResult } from './portal-auth.service';
import { PortalJwtGuard, PortalUser } from './portal-jwt.guard';
import { PortalJwtPayload } from './portal-jwt.util';
import { PortalPasswordResetService } from './portal-password-reset.service';
import {
  PortalChangePasswordResponse,
  PortalForgotPasswordResponse,
  PortalResetPasswordResponse,
  PortalValidateResetTokenResponse,
} from './portal-password-reset.types';

class PortalLoginBody {
  email!: string;
  password!: string;
}

class PortalRefreshBody {
  refresh_token!: string;
}

class PortalForgotPasswordBody {
  email!: string;
}

class PortalResetPasswordBody {
  token!: string;
  password!: string;
}

class PortalChangePasswordBody {
  current_password!: string;
  new_password!: string;
}

@Controller('api/v1/portal/auth')
export class PortalAuthController {
  constructor(
    private readonly auth: PortalAuthService,
    private readonly passwordReset: PortalPasswordResetService,
  ) {}

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

  @Post('forgot-password')
  @HttpCode(HttpStatus.OK)
  async forgotPassword(@Body() body: PortalForgotPasswordBody): Promise<PortalForgotPasswordResponse> {
    return this.passwordReset.forgotPassword(body.email ?? '');
  }

  @Get('reset-password/validate')
  async validateResetToken(@Query('token') token?: string): Promise<PortalValidateResetTokenResponse> {
    return this.passwordReset.validateResetToken(token ?? '');
  }

  @Post('reset-password')
  @HttpCode(HttpStatus.OK)
  async resetPassword(@Body() body: PortalResetPasswordBody): Promise<PortalResetPasswordResponse> {
    return this.passwordReset.resetPassword(body.token ?? '', body.password ?? '');
  }

  @Post('change-password')
  @HttpCode(HttpStatus.OK)
  @UseGuards(PortalJwtGuard)
  async changePassword(
    @PortalUser() user: PortalJwtPayload,
    @Body() body: PortalChangePasswordBody,
  ): Promise<PortalChangePasswordResponse> {
    return this.passwordReset.changePassword(
      user.sub,
      user.client_id,
      body.current_password ?? '',
      body.new_password ?? '',
    );
  }
}
