import { BadRequestException } from '@nestjs/common';
import { MetaCreativeRegistryService } from './meta-creative-registry.service';
import { MetaCreativeRegistryRepository } from './meta-creative-registry.repository';

describe('MetaCreativeRegistryService', () => {
  const repo = {
    pgReady: jest.fn(),
    clientExists: jest.fn(),
    getCreativeSubmission: jest.fn(),
    findActiveLink: jest.fn(),
    insertLink: jest.fn(),
    listLinks: jest.fn(),
    resolveLink: jest.fn(),
    deactivateLink: jest.fn(),
  } as unknown as MetaCreativeRegistryRepository;

  const service = new MetaCreativeRegistryService(repo);

  beforeEach(() => {
    jest.resetAllMocks();
    process.env.PTT_META_CREATIVE_REGISTRY_ENABLED = '1';
  });

  it('returns disabled list when flag off', async () => {
    process.env.PTT_META_CREATIVE_REGISTRY_ENABLED = '0';
    const out = await service.listLinks({});
    expect(out.disabled).toBe(true);
    expect(out.rows).toEqual([]);
  });

  it('rejects unapproved creative on create', async () => {
    (repo.pgReady as jest.Mock).mockResolvedValue(true);
    (repo.clientExists as jest.Mock).mockResolvedValue(true);
    (repo.getCreativeSubmission as jest.Mock).mockResolvedValue({
      id: 'cr1',
      client_id: 'c1',
      status: 'pending_client',
      title: 'T',
      asset_url: null,
      version: 1,
      external_campaign_id: 'camp1',
    });

    await expect(
      service.createLink({
        client_id: 'c1',
        creative_submission_id: 'cr1',
        external_ad_id: 'ad1',
      }),
    ).rejects.toBeInstanceOf(BadRequestException);
  });
});
