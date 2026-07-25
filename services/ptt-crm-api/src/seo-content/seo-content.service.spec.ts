import { SeoContentRepository } from './seo-content.repository';
import { SeoContentService } from './seo-content.service';

describe('SeoContentService', () => {
  const repo = {
    listKeywords: jest.fn(),
    listQuestions: jest.fn(),
    listEntityGroups: jest.fn(),
    listOpportunities: jest.fn(),
    listClusters: jest.fn(),
    previewBrief: jest.fn(),
    pipelineBoard: jest.fn(),
    getContentDetail: jest.fn(),
  } as unknown as SeoContentRepository;

  const service = new SeoContentService(repo);

  beforeEach(() => {
    jest.resetAllMocks();
  });

  it('loads full research console by default', async () => {
    (repo.listKeywords as jest.Mock).mockResolvedValue([{ id: 1 }]);
    (repo.listQuestions as jest.Mock).mockResolvedValue([]);
    (repo.listEntityGroups as jest.Mock).mockResolvedValue([]);
    (repo.listOpportunities as jest.Mock).mockResolvedValue([]);
    (repo.listClusters as jest.Mock).mockResolvedValue([]);
    const out = await service.researchConsole(5);
    expect(out.keywords).toHaveLength(1);
    expect(repo.listKeywords).toHaveBeenCalledWith(5, { limit: 100 });
  });

  it('loads keywords tab only', async () => {
    (repo.listKeywords as jest.Mock).mockResolvedValue([{ id: 2 }]);
    const out = await service.researchConsole(5, 'keywords');
    expect(out.keywords).toHaveLength(1);
    expect(out.questions).toEqual([]);
    expect(repo.listQuestions).not.toHaveBeenCalled();
  });

  it('returns pipeline board', async () => {
    (repo.pipelineBoard as jest.Mock).mockResolvedValue({ columns: [] });
    const out = await service.pipelineBoard(3);
    expect(out.columns).toEqual([]);
    expect(repo.pipelineBoard).toHaveBeenCalledWith(3, undefined);
  });
});
