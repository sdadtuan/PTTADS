import { Body, Controller, Get, Param, Patch, Post, Query } from '@nestjs/common';
import { EmailMarketingService } from './email-marketing.service';
import { EmailPreferencePublicView } from './email-marketing.types';

@Controller('api/v1/email/public')
export class EmailPublicController {
  constructor(private readonly email: EmailMarketingService) {}

  @Get('preferences/:token')
  async preferences(@Param('token') token: string): Promise<EmailPreferencePublicView> {
    return this.email.publicPreferences(token);
  }

  @Post('preferences/:token')
  async updatePreferences(
    @Param('token') token: string,
    @Body()
    body: { marketing?: boolean; topics?: Array<{ topic: string; opted_in: boolean }> },
  ): Promise<{ ok: boolean }> {
    return this.email.updatePublicPreferences(token, body);
  }

  @Post('unsubscribe/:token')
  async unsubscribe(@Param('token') token: string): Promise<{ ok: boolean; email: string }> {
    return this.email.publicUnsubscribe(token);
  }

  @Post('confirm/:token')
  async confirm(@Param('token') token: string): Promise<{ ok: boolean; email: string }> {
    return this.email.publicConfirm(token);
  }
}

@Controller('api/v1/email')
export class EmailCaptureController {
  constructor(private readonly email: EmailMarketingService) {}

  @Post('capture')
  async capture(
    @Body()
    body: {
      client_id: string;
      email: string;
      first_name?: string;
      source?: string;
    },
  ): Promise<{ ok: boolean; contact_id: string; confirm_token?: string }> {
    return this.email.capture(body);
  }
}
