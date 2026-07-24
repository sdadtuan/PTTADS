import {
  BadRequestException,
  Injectable,
  NotFoundException,
  ServiceUnavailableException,
} from '@nestjs/common';
import { MetaTrackingRepository } from './meta-tracking.repository';
import { TestPixelResponse } from './meta-tracking.types';

const GRAPH_VERSION = process.env.PTT_META_GRAPH_VERSION ?? 'v21.0';

@Injectable()
export class MetaPixelTestService {
  constructor(private readonly repo: MetaTrackingRepository) {}

  isTrackingEnabled(): boolean {
    return ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_META_TRACKING_ENABLED ?? '0').trim().toLowerCase(),
    );
  }

  private isStubMode(): boolean {
    return ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_CAPI_STUB ?? '0').trim().toLowerCase(),
    );
  }

  private testEventCode(): string {
    return (process.env.PTT_CAPI_TEST_EVENT_CODE ?? '').trim();
  }

  private resolveAccessToken(account: {
    access_token_encrypted: string | null;
    credential_ref: string | null;
  }): string {
    const global = (process.env.PTT_META_ACCESS_TOKEN ?? process.env.META_ACCESS_TOKEN ?? '').trim();
    if (global) return global;
    if (account.access_token_encrypted?.trim()) {
      return account.access_token_encrypted.trim();
    }
    const cred = account.credential_ref?.trim();
    if (cred && !cred.startsWith('vault:')) {
      return cred;
    }
    return '';
  }

  async testPixel(clientId: string, accountId: string): Promise<TestPixelResponse> {
    if (!this.isTrackingEnabled()) {
      throw new ServiceUnavailableException({ ok: false, error: 'meta_tracking_disabled' });
    }
    if (!(await this.repo.pgCapiEventLogReady())) {
      throw new ServiceUnavailableException({ ok: false, error: 'capi_event_log_not_ready' });
    }

    const account = await this.repo.getMetaChannelAccount(clientId.trim(), accountId.trim());
    if (!account) {
      throw new NotFoundException({ error: 'channel_account_not_found' });
    }
    if (!account.pixel_id) {
      throw new BadRequestException({ ok: false, error: 'pixel_not_configured' });
    }

    if (this.isStubMode()) {
      return {
        ok: true,
        stub: true,
        pixel_id: account.pixel_id,
        events_received: 1,
        fbtrace_id: null,
        graph_response: { events_received: 1, stub: true },
      };
    }

    const token = this.resolveAccessToken(account);
    if (!token) {
      throw new BadRequestException({ ok: false, error: 'missing_meta_access_token' });
    }

    const eventTime = Math.floor(Date.now() / 1000);
    const event = {
      event_name: 'PageView',
      event_time: eventTime,
      event_id: `ptt-pixel-test-${clientId}-${accountId}-${eventTime}`,
      action_source: 'website',
      user_data: {
        client_ip_address: '127.0.0.1',
        client_user_agent: 'PTTADS/meta-tracking-test',
      },
    };

    const body: Record<string, unknown> = {
      data: [event],
      access_token: token,
    };
    const testCode = this.testEventCode();
    if (testCode) {
      body.test_event_code = testCode;
    }

    const url = `https://graph.facebook.com/${GRAPH_VERSION}/${encodeURIComponent(account.pixel_id)}/events`;
    let response: Response;
    try {
      response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'graph_network_error';
      return { ok: false, pixel_id: account.pixel_id, error: message };
    }

    const raw = (await response.json().catch(() => ({}))) as Record<string, unknown>;
    if (!response.ok) {
      const graphErr = raw.error as Record<string, unknown> | undefined;
      const message = String(graphErr?.message ?? response.statusText ?? 'graph_error');
      return {
        ok: false,
        pixel_id: account.pixel_id,
        error: message,
        graph_response: raw,
      };
    }

    return {
      ok: true,
      pixel_id: account.pixel_id,
      events_received:
        raw.events_received != null ? Number(raw.events_received) : undefined,
      fbtrace_id: raw.fbtrace_id != null ? String(raw.fbtrace_id) : null,
      graph_response: raw,
    };
  }
}
