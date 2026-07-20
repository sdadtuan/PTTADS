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
  UseGuards,
} from '@nestjs/common';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { CatalogService } from './catalog.service';
import {
  CreateAssignScopeBody,
  CreateCatalogIndustryBody,
  CreateCatalogServiceBody,
  PatchAssignScopeBody,
  PatchCatalogIndustryBody,
  PatchCatalogServiceBody,
} from './catalog.types';
import { StaffCatalogConfigureGuard, StaffCatalogViewGuard } from './guards/staff-catalog.guard';

@Controller('api/crm/catalog')
@UseGuards(StaffOrInternalKeyGuard, StaffCatalogViewGuard)
export class CatalogController {
  constructor(private readonly catalog: CatalogService) {}

  @Get()
  getPublic() {
    return this.catalog.publicPayload();
  }

  @Get('services')
  listServices() {
    return { services: this.catalog.listServices() };
  }

  @Post('services')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffCatalogConfigureGuard)
  createService(@Body() body: CreateCatalogServiceBody) {
    return { service: this.catalog.createService(body) };
  }

  @Patch('services/:id')
  @UseGuards(StaffCatalogConfigureGuard)
  patchService(@Param('id', ParseIntPipe) id: number, @Body() body: PatchCatalogServiceBody) {
    return { service: this.catalog.updateService(id, body) };
  }

  @Get('industries')
  listIndustries() {
    return { industries: this.catalog.listIndustries() };
  }

  @Post('industries')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffCatalogConfigureGuard)
  createIndustry(@Body() body: CreateCatalogIndustryBody) {
    return { industry: this.catalog.createIndustry(body) };
  }

  @Patch('industries/:id')
  @UseGuards(StaffCatalogConfigureGuard)
  patchIndustry(@Param('id', ParseIntPipe) id: number, @Body() body: PatchCatalogIndustryBody) {
    return { industry: this.catalog.updateIndustry(id, body) };
  }
}

@Controller('api/crm/assign-scopes')
@UseGuards(StaffOrInternalKeyGuard, StaffCatalogViewGuard)
export class AssignScopesController {
  constructor(private readonly catalog: CatalogService) {}

  @Get()
  list() {
    return this.catalog.listAssignScopes();
  }

  @Post()
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffCatalogConfigureGuard)
  create(@Body() body: CreateAssignScopeBody) {
    return { scope: this.catalog.createAssignScope(body) };
  }

  @Patch(':id')
  @UseGuards(StaffCatalogConfigureGuard)
  patch(@Param('id', ParseIntPipe) id: number, @Body() body: PatchAssignScopeBody) {
    return { scope: this.catalog.updateAssignScope(id, body) };
  }

  @Delete(':id')
  @UseGuards(StaffCatalogConfigureGuard)
  remove(@Param('id', ParseIntPipe) id: number) {
    this.catalog.deleteAssignScope(id);
    return { ok: true };
  }
}
