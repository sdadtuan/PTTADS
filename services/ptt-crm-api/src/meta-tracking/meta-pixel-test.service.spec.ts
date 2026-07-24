import { BadRequestException, ServiceUnavailableException } from '@nestjs/common';
import { MetaPixelTestService } from './meta-pixel-test.service';
import { MetaTrackingRepository } from './meta-tracking.repository';

describe('MetaPixelTestService', () => {
  const repo = {
    pgCapiEventLogReady: jest.fn(),
    getMetaChannelAccount: jest.fn(),
    recordPixelTestResult: jest.fn().mockResolvedValue(undefined),
  } as unknown as MetaTrackingRepository;

  beforeEach(() => {
    jest.resetAllMocks();
    delete process.env.PTT_META_TRACKING_ENABLED;
    delete process.env.PTT_CAPI_STUB;
  });

  it('throws when tracking disabled', async () => {
    const svc = new MetaPixelTestService(repo);
    await expect(svc.testPixel('c1', 'a1')).rejects.toBeInstanceOf(ServiceUnavailableException);
  });

  it('returns stub response in CAPI stub mode', async () => {
    process.env.PTT_META_TRACKING_ENABLED = '1';
    process.env.PTT_CAPI_STUB = '1';
    (repo.pgCapiEventLogReady as jest.Mock).mockResolvedValue(true);
    (repo.getMetaChannelAccount as jest.Mock).mockResolvedValue({
      client_id: 'c1',
      account_id: 'a1',
      pixel_id: '123456',
      access_token_encrypted: null,
      credential_ref: null,
      meta: {},
    });

    const svc = new MetaPixelTestService(repo);
    const out = await svc.testPixel('c1', 'a1');
    expect(out.ok).toBe(true);
    expect(out.stub).toBe(true);
    expect(out.pixel_id).toBe('123456');
  });

  it('errors when pixel missing', async () => {
    process.env.PTT_META_TRACKING_ENABLED = '1';
    process.env.PTT_CAPI_STUB = '1';
    (repo.pgCapiEventLogReady as jest.Mock).mockResolvedValue(true);
    (repo.getMetaChannelAccount as jest.Mock).mockResolvedValue({
      client_id: 'c1',
      account_id: 'a1',
      pixel_id: null,
      access_token_encrypted: null,
      credential_ref: null,
      meta: {},
    });

    const svc = new MetaPixelTestService(repo);
    await expect(svc.testPixel('c1', 'a1')).rejects.toBeInstanceOf(BadRequestException);
  });
});
