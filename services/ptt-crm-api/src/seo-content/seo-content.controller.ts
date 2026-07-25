import {
  Body,
  Controller,
  Get,
  NotFoundException,
  Param,
  ParseIntPipe,
  Patch,
  Post,
  Query,
  Req,
  UseGuards,
} from '@nestjs/common';
import { Request } from 'express';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { StaffJwtPayload } from '../staff-auth/staff-jwt.util';
import {
  StaffSeoApproveGuard,
  StaffSeoSettingsGuard,
  StaffSeoViewGuard,
  StaffSeoWriteGuard,
} from '../seo-admin/guards/staff-seo-view.guard';
import { SeoContentService } from './seo-content.service';

type StaffReq = Request & { staffUser?: StaffJwtPayload; staffAuthVia?: 'internal' | 'jwt' };

function actorId(req: StaffReq): string {
  if (req.staffAuthVia === 'internal') return 'internal';
  return String(req.staffUser?.sub ?? req.staffUser?.email ?? 'staff');
}

@Controller('api/v1/seo')
@UseGuards(StaffOrInternalKeyGuard, StaffSeoViewGuard)
export class SeoContentController {
  constructor(private readonly content: SeoContentService) {}

  @Get('clients/:id/research')
  async researchConsole(@Param('id', ParseIntPipe) id: number, @Query('tab') tab?: string) {
    const data = await this.content.researchConsole(id, tab);
    return { ok: true, customer_id: id, ...data };
  }

  @Get('clients/:id/keywords')
  async keywords(
    @Param('id', ParseIntPipe) id: number,
    @Query('q') q?: string,
    @Query('intent') intent?: string,
    @Query('cluster_id') clusterId?: string,
  ) {
    const keywords = await this.content.listKeywords(id, {
      q,
      intent,
      clusterId: clusterId ? Number.parseInt(clusterId, 10) : undefined,
    });
    return { ok: true, keywords };
  }

  @Post('clients/:id/keywords')
  @UseGuards(StaffSeoWriteGuard)
  async createKeyword(@Param('id', ParseIntPipe) id: number, @Body() body: Record<string, unknown>) {
    const keyword = await this.content.createKeyword(id, body);
    return { ok: true, keyword };
  }

  @Post('clients/:id/keywords/import')
  @UseGuards(StaffSeoWriteGuard)
  async importKeywords(@Param('id', ParseIntPipe) id: number, @Body() body: { csv?: string }) {
    return this.content.importKeywordsCsv(id, String(body.csv ?? ''));
  }

  @Get('clients/:id/questions')
  async questions(@Param('id', ParseIntPipe) id: number, @Query('q') q?: string) {
    const items = await this.content.listQuestions(id, { q });
    return { ok: true, questions: items };
  }

  @Post('clients/:id/questions')
  @UseGuards(StaffSeoWriteGuard)
  async createQuestion(@Param('id', ParseIntPipe) id: number, @Body() body: Record<string, unknown>) {
    const question = await this.content.createQuestion(id, body);
    return { ok: true, question };
  }

  @Get('clients/:id/clusters')
  async clusters(@Param('id', ParseIntPipe) id: number) {
    const clusters = await this.content.listClusters(id);
    return { ok: true, clusters };
  }

  @Post('clients/:id/clusters')
  @UseGuards(StaffSeoWriteGuard)
  async createCluster(@Param('id', ParseIntPipe) id: number, @Body() body: Record<string, unknown>) {
    const cluster = await this.content.createCluster(id, body);
    return { ok: true, cluster };
  }

  @Post('clients/:id/research/serp')
  @UseGuards(StaffSeoWriteGuard)
  async captureSerp(
    @Param('id', ParseIntPipe) id: number,
    @Body() body: { phrase?: string; keyword_id?: number; domain_hint?: string },
  ) {
    const snapshot = await this.content.captureSerpSnapshot(id, body);
    return { ok: true, snapshot };
  }

  @Post('clients/:id/research/pages/sync-gsc')
  @UseGuards(StaffSeoWriteGuard)
  async syncPagesFromGsc(
    @Param('id', ParseIntPipe) id: number,
    @Body() body: { days?: number },
  ) {
    const out = await this.content.syncPagesFromGsc(id, body.days);
    return { ok: true, ...out };
  }

  @Post('clients/:id/entities/autolink')
  @UseGuards(StaffSeoWriteGuard)
  async autolinkEntities(@Param('id', ParseIntPipe) id: number) {
    const out = await this.content.autolinkEntities(id);
    return { ok: true, ...out };
  }

  @Post('research/brief-preview')
  async briefPreview(
    @Body()
    body: {
      customer_id: number;
      keyword_id?: number;
      question_id?: number;
    },
  ) {
    const preview = await this.content.previewBrief({
      customerId: Number(body.customer_id),
      keywordId: body.keyword_id,
      questionId: body.question_id,
    });
    return { ok: true, ...preview };
  }

  @Post('research/to-content')
  @UseGuards(StaffSeoWriteGuard)
  async toContent(
    @Req() req: StaffReq,
    @Body()
    body: {
      customer_id: number;
      keyword_id?: number;
      question_id?: number;
      lifecycle_id?: number;
      project_id?: number;
      title?: string;
      brief?: Record<string, unknown>;
      owner_staff_id?: number;
      due_date?: string;
    },
  ) {
    const content = await this.content.createFromResearch({
      customerId: Number(body.customer_id),
      keywordId: body.keyword_id,
      questionId: body.question_id,
      lifecycleId: body.lifecycle_id,
      projectId: body.project_id,
      title: body.title,
      brief: body.brief,
      ownerStaffId: body.owner_staff_id,
      dueDate: body.due_date,
      actorId: actorId(req),
    });
    return { ok: true, content };
  }

  @Get('content/pipeline')
  async pipeline(
    @Query('customer_id') customerId?: string,
    @Query('lifecycle_id') lifecycleId?: string,
  ) {
    const board = await this.content.pipelineBoard(
      customerId ? Number.parseInt(customerId, 10) : undefined,
      lifecycleId ? Number.parseInt(lifecycleId, 10) : undefined,
    );
    return { ok: true, board };
  }

  @Get('clients/:id/content')
  async listClientContent(
    @Param('id', ParseIntPipe) id: number,
    @Query('workflow_status') workflowStatus?: string,
  ) {
    const items = await this.content.listContent({ customerId: id, workflowStatus });
    return { ok: true, content: items };
  }

  @Post('clients/:id/content')
  @UseGuards(StaffSeoWriteGuard)
  async createClientContent(
    @Req() req: StaffReq,
    @Param('id', ParseIntPipe) id: number,
    @Body() body: Record<string, unknown>,
  ) {
    const content = await this.content.createContent({
      ...body,
      customer_id: id,
      actor_id: actorId(req),
    });
    return { ok: true, content };
  }

  @Get('content/:id')
  async getContent(@Param('id', ParseIntPipe) id: number) {
    const content = await this.content.getContent(id);
    if (!content) throw new NotFoundException({ error: 'content_not_found' });
    return { ok: true, content };
  }

  @Patch('content/:id')
  @UseGuards(StaffSeoWriteGuard)
  async patchContent(@Param('id', ParseIntPipe) id: number, @Body() body: Record<string, unknown>) {
    const content = await this.content.updateContent(id, body);
    return { ok: true, content };
  }

  @Patch('content/:id/status')
  @UseGuards(StaffSeoWriteGuard)
  async patchStatus(
    @Req() req: StaffReq,
    @Param('id', ParseIntPipe) id: number,
    @Body() body: { workflow_status: string; notes?: string },
  ) {
    const content = await this.content.transitionStatus(
      id,
      body.workflow_status,
      actorId(req),
      body.notes ?? '',
    );
    return { ok: true, content };
  }

  @Post('content/:id/approve')
  @UseGuards(StaffSeoApproveGuard)
  async approveContent(
    @Req() req: StaffReq,
    @Param('id', ParseIntPipe) id: number,
    @Body() body: { stage: string; approved: boolean; notes?: string },
  ) {
    const content = await this.content.approveStage({
      contentId: id,
      stage: body.stage,
      approved: body.approved,
      actorId: actorId(req),
      notes: body.notes ?? '',
    });
    return { ok: true, content };
  }

  @Get('content/:id/versions')
  async listVersions(@Param('id', ParseIntPipe) id: number) {
    const versions = await this.content.listVersions(id);
    return { ok: true, versions };
  }

  @Get('content/:id/versions/:vid')
  async getVersion(@Param('id', ParseIntPipe) id: number, @Param('vid', ParseIntPipe) vid: number) {
    const version = await this.content.getVersion(id, vid);
    if (!version) throw new NotFoundException({ error: 'version_not_found' });
    return { ok: true, version };
  }

  @Post('content/:id/versions')
  @UseGuards(StaffSeoWriteGuard)
  async saveVersion(
    @Req() req: StaffReq,
    @Param('id', ParseIntPipe) id: number,
    @Body() body: { body_html: string; changes_summary?: string },
  ) {
    const version = await this.content.saveVersion({
      contentId: id,
      bodyHtml: body.body_html,
      changesSummary: body.changes_summary,
      createdBy: actorId(req),
    });
    return { ok: true, version };
  }

  @Get('content/:id/aeo-checklist')
  async aeoChecklist(@Param('id', ParseIntPipe) id: number) {
    const checklist = await this.content.aeoChecklist(id);
    return { ok: true, checklist };
  }
}
