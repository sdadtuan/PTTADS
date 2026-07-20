import { BadRequestException, Injectable } from '@nestjs/common';
import { CatalogSqliteRepository } from './catalog-sqlite.repository';
import {
  AssignScopeRow,
  CatalogIndustryRow,
  CatalogPublicPayload,
  CatalogServiceRow,
  CreateAssignScopeBody,
  CreateCatalogIndustryBody,
  CreateCatalogServiceBody,
  PatchAssignScopeBody,
  PatchCatalogIndustryBody,
  PatchCatalogServiceBody,
  StaffOption,
} from './catalog.types';

@Injectable()
export class CatalogService {
  constructor(private readonly repo: CatalogSqliteRepository) {}

  private wrap<T>(fn: () => T): T {
    try {
      return fn();
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      throw new BadRequestException({ error: message });
    }
  }

  publicPayload(): CatalogPublicPayload {
    return this.repo.publicPayload();
  }

  listServices(): CatalogServiceRow[] {
    return this.repo.listServices(false);
  }

  listIndustries(): CatalogIndustryRow[] {
    return this.repo.listIndustries(false);
  }

  createService(body: CreateCatalogServiceBody): CatalogServiceRow {
    return this.wrap(() => this.repo.createService(body));
  }

  updateService(id: number, body: PatchCatalogServiceBody): CatalogServiceRow {
    return this.wrap(() => this.repo.updateService(id, body));
  }

  createIndustry(body: CreateCatalogIndustryBody): CatalogIndustryRow {
    return this.wrap(() => this.repo.createIndustry(body));
  }

  updateIndustry(id: number, body: PatchCatalogIndustryBody): CatalogIndustryRow {
    return this.wrap(() => this.repo.updateIndustry(id, body));
  }

  listAssignScopes(): { scopes: AssignScopeRow[]; staff: StaffOption[] } {
    return this.repo.listAssignScopes();
  }

  createAssignScope(body: CreateAssignScopeBody): AssignScopeRow {
    return this.wrap(() => this.repo.createAssignScope(body));
  }

  updateAssignScope(id: number, body: PatchAssignScopeBody): AssignScopeRow {
    return this.wrap(() => this.repo.updateAssignScope(id, body));
  }

  deleteAssignScope(id: number): void {
    this.wrap(() => this.repo.deleteAssignScope(id));
  }
}
