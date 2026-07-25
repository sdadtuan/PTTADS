import { Injectable } from '@nestjs/common';
import { SeoContentRepository } from './seo-content.repository';
import {
  SeoBriefPreviewResponse,
  SeoClusterRow,
  SeoContentRow,
  SeoContentVersionRow,
  SeoKeywordRow,
  SeoPipelineBoard,
  SeoQuestionRow,
  SeoResearchConsoleResponse,
  SeoAeoChecklistResponse,
} from './seo-content.types';

@Injectable()
export class SeoContentService {
  constructor(private readonly repo: SeoContentRepository) {}

  researchConsole(customerId: number, tab?: string): Promise<SeoResearchConsoleResponse> {
    return this.repoResearchConsole(customerId, tab);
  }

  private async repoResearchConsole(customerId: number, tab?: string): Promise<SeoResearchConsoleResponse> {
    const activeTab = tab?.trim().toLowerCase();
    if (activeTab === 'keywords') {
      const keywords = await this.repo.listKeywords(customerId);
      return { keywords, questions: [], entities: [], opportunities: [], clusters: [] };
    }
    if (activeTab === 'questions') {
      const questions = await this.repo.listQuestions(customerId);
      return { keywords: [], questions, entities: [], opportunities: [], clusters: [] };
    }
    if (activeTab === 'entities') {
      const entities = await this.repo.listEntityGroups(customerId);
      return { keywords: [], questions: [], entities, opportunities: [], clusters: [] };
    }
    if (activeTab === 'clusters') {
      const clusters = await this.repo.listClusters(customerId);
      return { keywords: [], questions: [], entities: [], opportunities: [], clusters };
    }
    if (activeTab === 'opportunities') {
      const opportunities = await this.repo.listOpportunities(customerId);
      return { keywords: [], questions: [], entities: [], opportunities, clusters: [] };
    }
    const [keywords, questions, entities, opportunities, clusters] = await Promise.all([
      this.repo.listKeywords(customerId, { limit: 100 }),
      this.repo.listQuestions(customerId, { limit: 100 }),
      this.repo.listEntityGroups(customerId),
      this.repo.listOpportunities(customerId, 40, 50),
      this.repo.listClusters(customerId),
    ]);
    return { keywords, questions, entities, opportunities, clusters };
  }

  listKeywords(customerId: number, params?: { q?: string; intent?: string; clusterId?: number }) {
    return this.repo.listKeywords(customerId, params);
  }

  createKeyword(customerId: number, payload: Record<string, unknown>): Promise<SeoKeywordRow> {
    return this.repo.createKeyword(customerId, payload);
  }

  importKeywordsCsv(customerId: number, csvText: string): Promise<{ ok: boolean; imported: number }> {
    return this.repo.importKeywordsCsv(customerId, csvText).then((imported) => ({ ok: true, imported }));
  }

  listQuestions(customerId: number, params?: { q?: string }) {
    return this.repo.listQuestions(customerId, params);
  }

  createQuestion(customerId: number, payload: Record<string, unknown>): Promise<SeoQuestionRow> {
    return this.repo.createQuestion(customerId, payload);
  }

  listClusters(customerId: number) {
    return this.repo.listClusters(customerId);
  }

  createCluster(customerId: number, payload: Record<string, unknown>): Promise<SeoClusterRow> {
    return this.repo.createCluster(customerId, payload);
  }

  previewBrief(params: {
    customerId: number;
    keywordId?: number;
    questionId?: number;
  }): Promise<SeoBriefPreviewResponse> {
    return this.repo.previewBrief(params);
  }

  createFromResearch(params: {
    customerId: number;
    keywordId?: number;
    questionId?: number;
    lifecycleId?: number;
    projectId?: number;
    title?: string;
    brief?: Record<string, unknown>;
    ownerStaffId?: number;
    dueDate?: string;
    actorId?: string;
  }): Promise<SeoContentRow> {
    return this.repo.createContentFromResearch(params);
  }

  pipelineBoard(customerId?: number, lifecycleId?: number): Promise<SeoPipelineBoard> {
    return this.repo.pipelineBoard(customerId, lifecycleId);
  }

  listContent(params: {
    customerId?: number;
    lifecycleId?: number;
    workflowStatus?: string;
  }) {
    return this.repo.listContent(params);
  }

  getContent(contentId: number) {
    return this.repo.getContentDetail(contentId);
  }

  createContent(payload: Record<string, unknown>) {
    return this.repo.createContent(payload);
  }

  updateContent(contentId: number, payload: Record<string, unknown>) {
    return this.repo.updateContent(contentId, payload);
  }

  transitionStatus(contentId: number, targetStatus: string, actorId: string, notes: string) {
    return this.repo.transitionStatus(contentId, targetStatus, actorId, notes);
  }

  approveStage(params: {
    contentId: number;
    stage: string;
    approved: boolean;
    actorId: string;
    notes: string;
  }) {
    return this.repo.approveStage(params);
  }

  listVersions(contentId: number) {
    return this.repo.listVersions(contentId);
  }

  getVersion(contentId: number, versionId: number) {
    return this.repo.getVersion(contentId, versionId);
  }

  saveVersion(params: {
    contentId: number;
    bodyHtml: string;
    changesSummary?: string;
    createdBy?: string;
  }): Promise<SeoContentVersionRow> {
    return this.repo.saveVersion(params);
  }

  aeoChecklist(contentId: number): Promise<SeoAeoChecklistResponse> {
    return this.repo.aeoChecklist(contentId);
  }
}
