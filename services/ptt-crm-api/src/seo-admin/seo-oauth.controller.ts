import { Controller, Get, Query, Res } from '@nestjs/common';
import { Response } from 'express';
import { SeoAdminService } from './seo-admin.service';

/** Public OAuth callbacks — no staff JWT (Google redirect). */
@Controller('api/v1/seo')
export class SeoOAuthCallbackController {
  constructor(private readonly seo: SeoAdminService) {}

  @Get('gsc/oauth/callback')
  async gscCallback(
    @Query('code') code: string,
    @Query('state') state: string,
    @Query('error') error: string | undefined,
    @Res() res: Response,
  ): Promise<void> {
    const redirect = await this.seo.oauthCallback('gsc', code, state, error);
    res.redirect(302, redirect);
  }

  @Get('ga4/oauth/callback')
  async ga4Callback(
    @Query('code') code: string,
    @Query('state') state: string,
    @Query('error') error: string | undefined,
    @Res() res: Response,
  ): Promise<void> {
    const redirect = await this.seo.oauthCallback('ga4', code, state, error);
    res.redirect(302, redirect);
  }
}
