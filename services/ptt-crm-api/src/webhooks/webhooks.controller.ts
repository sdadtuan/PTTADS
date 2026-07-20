import { Controller, Get, Param, Post, Req, Res, UseGuards } from '@nestjs/common';
import { Request, Response } from 'express';
import { WebhooksEnabledGuard } from './guards/webhooks-enabled.guard';
import { WebhooksService } from './webhooks.service';

@Controller('api/v1')
@UseGuards(WebhooksEnabledGuard)
export class WebhooksController {
  constructor(private readonly webhooks: WebhooksService) {}

  @Get('channels')
  listChannels(): Record<string, unknown> {
    return this.webhooks.listChannels();
  }

  @Get('webhooks/:channel')
  async getWebhook(
    @Param('channel') channel: string,
    @Req() req: Request,
    @Res({ passthrough: true }) res: Response,
  ): Promise<Record<string, unknown> | string> {
    return this.dispatch(channel, req, res);
  }

  @Post('webhooks/:channel')
  async postWebhook(
    @Param('channel') channel: string,
    @Req() req: Request,
    @Res({ passthrough: true }) res: Response,
  ): Promise<Record<string, unknown> | string> {
    return this.dispatch(channel, req, res);
  }

  private async dispatch(
    channel: string,
    req: Request,
    res: Response,
  ): Promise<Record<string, unknown> | string> {
    const out = await this.webhooks.handle(channel, req);
    res.status(out.status);
    if (out.contentType) {
      res.setHeader('Content-Type', out.contentType);
    }
    if (out.kind === 'challenge') {
      return out.body as string;
    }
    return out.body as Record<string, unknown>;
  }
}
