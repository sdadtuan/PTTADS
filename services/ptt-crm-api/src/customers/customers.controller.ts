import {
  Body,
  Controller,
  Delete,
  Get,
  HttpCode,
  HttpStatus,
  Param,
  ParseIntPipe,
  Patch,
  Post,
  Query,
  UseGuards,
} from '@nestjs/common';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { CustomersService } from './customers.service';
import {
  CreateCustomerBody,
  CreateIssueBody,
  CreatePurchaseBody,
  CreateRelationBody,
  GenerateBriefBody,
  PatchCustomerBody,
  PatchIssueBody,
  PatchPurchaseBody,
  PatchRelationBody,
} from './customers.types';
import { StaffCustomersViewGuard, StaffCustomersWriteGuard } from './guards/staff-customers.guard';

@Controller('api/crm/customers')
@UseGuards(StaffOrInternalKeyGuard, StaffCustomersViewGuard)
export class CustomersController {
  constructor(private readonly customers: CustomersService) {}

  @Get()
  list(@Query('q') q?: string, @Query('limit') limit?: string) {
    const lim = limit ? Number(limit) : undefined;
    return this.customers.list(q, lim);
  }

  @Get(':id/brief/latest')
  latestBrief(@Param('id', ParseIntPipe) id: number) {
    return this.customers.latestBrief(id);
  }

  @Post(':id/brief/generate')
  @UseGuards(StaffCustomersWriteGuard)
  generateBrief(@Param('id', ParseIntPipe) id: number, @Body() body: GenerateBriefBody) {
    return this.customers.generateBrief(id, body);
  }

  @Post(':id/relations')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffCustomersWriteGuard)
  createRelation(@Param('id', ParseIntPipe) id: number, @Body() body: CreateRelationBody) {
    return this.customers.createRelation(id, body);
  }

  @Patch(':id/relations/:relationId')
  @UseGuards(StaffCustomersWriteGuard)
  patchRelation(
    @Param('id', ParseIntPipe) id: number,
    @Param('relationId', ParseIntPipe) relationId: number,
    @Body() body: PatchRelationBody,
  ) {
    return this.customers.patchRelation(id, relationId, body);
  }

  @Delete(':id/relations/:relationId')
  @UseGuards(StaffCustomersWriteGuard)
  deleteRelation(
    @Param('id', ParseIntPipe) id: number,
    @Param('relationId', ParseIntPipe) relationId: number,
  ) {
    return this.customers.deleteRelation(id, relationId);
  }

  @Post(':id/purchases')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffCustomersWriteGuard)
  createPurchase(@Param('id', ParseIntPipe) id: number, @Body() body: CreatePurchaseBody) {
    return this.customers.createPurchase(id, body);
  }

  @Patch(':id/purchases/:purchaseId')
  @UseGuards(StaffCustomersWriteGuard)
  patchPurchase(
    @Param('id', ParseIntPipe) id: number,
    @Param('purchaseId', ParseIntPipe) purchaseId: number,
    @Body() body: PatchPurchaseBody,
  ) {
    return this.customers.patchPurchase(id, purchaseId, body);
  }

  @Delete(':id/purchases/:purchaseId')
  @UseGuards(StaffCustomersWriteGuard)
  deletePurchase(
    @Param('id', ParseIntPipe) id: number,
    @Param('purchaseId', ParseIntPipe) purchaseId: number,
  ) {
    return this.customers.deletePurchase(id, purchaseId);
  }

  @Post(':id/issues')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffCustomersWriteGuard)
  createIssue(@Param('id', ParseIntPipe) id: number, @Body() body: CreateIssueBody) {
    return this.customers.createIssue(id, body);
  }

  @Patch(':id/issues/:issueId')
  @UseGuards(StaffCustomersWriteGuard)
  patchIssue(
    @Param('id', ParseIntPipe) id: number,
    @Param('issueId', ParseIntPipe) issueId: number,
    @Body() body: PatchIssueBody,
  ) {
    return this.customers.patchIssue(id, issueId, body);
  }

  @Get(':id')
  detail(@Param('id', ParseIntPipe) id: number) {
    return this.customers.detail(id);
  }

  @Post()
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffCustomersWriteGuard)
  create(@Body() body: CreateCustomerBody) {
    return this.customers.create(body);
  }

  @Patch(':id')
  @UseGuards(StaffCustomersWriteGuard)
  patch(@Param('id', ParseIntPipe) id: number, @Body() body: PatchCustomerBody) {
    return this.customers.patch(id, body);
  }
}
