import {
  Body,
  Controller,
  Delete,
  Get,
  HttpCode,
  HttpStatus,
  Param,
  ParseIntPipe,
  Post,
  Put,
  Query,
  UseGuards,
} from '@nestjs/common';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import {
  StaffReProjectsBudgetDeleteGuard,
  StaffReProjectsBudgetExportGuard,
  StaffReProjectsBudgetViewGuard,
  StaffReProjectsBudgetWriteGuard,
  StaffReProjectsDeleteGuard,
  StaffReProjectsKpiDeleteGuard,
  StaffReProjectsKpiViewGuard,
  StaffReProjectsKpiWriteGuard,
  StaffReProjectsProductsDeleteGuard,
  StaffReProjectsProductsViewGuard,
  StaffReProjectsProductsWriteGuard,
  StaffReProjectsExportGuard,
  StaffReProjectsRisksDeleteGuard,
  StaffReProjectsRisksViewGuard,
  StaffReProjectsRisksWriteGuard,
  StaffReProjectsUpdateGuard,
  StaffReProjectsViewGuard,
  StaffReProjectsWriteGuard,
} from './guards/staff-re-projects.guard';
import { ReProjectsAccountingService } from './re-projects-accounting.service';
import { ReProjectsKpiBudgetService } from './re-projects-kpi-budget.service';
import { ReProjectsOpsService } from './re-projects-ops.service';
import { ReProjectsService } from './re-projects.service';
import {
  AccountingAiAskBody,
  AddProjectStaffBody,
  ApplyPredictedRisksBody,
  CreateReProjectBody,
  ImportCashFlowBody,
  RefreshLeadsNewKpiBody,
  SaveBudgetLineBody,
  SaveCashFlowBody,
  SaveKpiBody,
  SavePriceListBody,
  SaveProductBody,
  SaveProjectLeadConfigBody,
  SaveProjectTypeBody,
  SaveRiskBody,
  UpdateProjectStaffBody,
} from './re-projects.types';

@Controller('api/crm/re-projects')
@UseGuards(StaffOrInternalKeyGuard)
export class ReProjectsController {
  constructor(
    private readonly reProjects: ReProjectsService,
    private readonly reProjectsAccounting: ReProjectsAccountingService,
    private readonly reProjectsKpiBudget: ReProjectsKpiBudgetService,
    private readonly reProjectsOps: ReProjectsOpsService,
  ) {}

  @Get('kpi-metrics')
  @UseGuards(StaffReProjectsKpiViewGuard)
  listKpiMetrics(@Query('re_only') reOnly?: string) {
    const raw = String(reOnly ?? '1').trim().toLowerCase();
    const reOnlyFlag = ['1', 'true', 'yes'].includes(raw);
    return this.reProjectsKpiBudget.listKpiMetrics(reOnlyFlag);
  }

  @Get('types')
  @UseGuards(StaffReProjectsViewGuard)
  listTypes(@Query('include_inactive') includeInactive?: string) {
    const raw = String(includeInactive ?? '').trim().toLowerCase();
    const include = ['1', 'true', 'yes', 'all'].includes(raw);
    return this.reProjects.listTypes(include);
  }

  @Post('types')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffReProjectsWriteGuard)
  createType(@Body() body: SaveProjectTypeBody) {
    return this.reProjects.createType(body);
  }

  @Put('types/:typeId')
  @UseGuards(StaffReProjectsWriteGuard)
  updateType(@Param('typeId', ParseIntPipe) typeId: number, @Body() body: SaveProjectTypeBody) {
    return this.reProjects.updateType(typeId, body);
  }

  @Delete('types/:typeId')
  @UseGuards(StaffReProjectsDeleteGuard)
  deleteType(@Param('typeId', ParseIntPipe) typeId: number) {
    return this.reProjects.deleteType(typeId);
  }

  @Get()
  @UseGuards(StaffReProjectsViewGuard)
  listProjects(@Query('q') q?: string) {
    return this.reProjects.listProjects(q);
  }

  @Post()
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffReProjectsWriteGuard)
  createProject(@Body() body: CreateReProjectBody) {
    return this.reProjects.createProject(body);
  }

  @Get(':id/kpis')
  @UseGuards(StaffReProjectsKpiViewGuard)
  listKpis(@Param('id', ParseIntPipe) id: number) {
    return this.reProjectsKpiBudget.listKpis(id);
  }

  @Post(':id/kpis')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffReProjectsKpiWriteGuard)
  createKpi(@Param('id', ParseIntPipe) id: number, @Body() body: SaveKpiBody) {
    return this.reProjectsKpiBudget.createKpi(id, body);
  }

  @Put(':id/kpis/:kpiId')
  @UseGuards(StaffReProjectsKpiWriteGuard)
  updateKpi(
    @Param('id', ParseIntPipe) id: number,
    @Param('kpiId', ParseIntPipe) kpiId: number,
    @Body() body: SaveKpiBody,
  ) {
    return this.reProjectsKpiBudget.updateKpi(id, kpiId, body);
  }

  @Delete(':id/kpis/:kpiId')
  @UseGuards(StaffReProjectsKpiDeleteGuard)
  deleteKpi(
    @Param('id', ParseIntPipe) id: number,
    @Param('kpiId', ParseIntPipe) kpiId: number,
  ) {
    return this.reProjectsKpiBudget.deleteKpi(id, kpiId);
  }

  @Post(':id/kpis/sync-to-staff')
  @UseGuards(StaffReProjectsKpiWriteGuard)
  syncKpisToStaff(@Param('id', ParseIntPipe) id: number) {
    return this.reProjectsKpiBudget.syncKpisToStaff(id);
  }

  @Post(':id/kpis/pull-from-staff')
  @UseGuards(StaffReProjectsKpiWriteGuard)
  pullKpisFromStaff(@Param('id', ParseIntPipe) id: number) {
    return this.reProjectsKpiBudget.pullKpisFromStaff(id);
  }

  @Post(':id/kpis/refresh-leads-new')
  @UseGuards(StaffReProjectsKpiWriteGuard)
  refreshLeadsNewKpi(@Param('id', ParseIntPipe) id: number, @Body() body: RefreshLeadsNewKpiBody) {
    return this.reProjectsKpiBudget.refreshLeadsNewKpi(id, body);
  }

  @Get(':id/risks')
  @UseGuards(StaffReProjectsRisksViewGuard)
  listRisks(@Param('id', ParseIntPipe) id: number) {
    return this.reProjectsKpiBudget.listRisks(id);
  }

  @Post(':id/risks')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffReProjectsRisksWriteGuard)
  createRisk(@Param('id', ParseIntPipe) id: number, @Body() body: SaveRiskBody) {
    return this.reProjectsKpiBudget.createRisk(id, body);
  }

  @Put(':id/risks/:riskId')
  @UseGuards(StaffReProjectsRisksWriteGuard)
  updateRisk(
    @Param('id', ParseIntPipe) id: number,
    @Param('riskId', ParseIntPipe) riskId: number,
    @Body() body: SaveRiskBody,
  ) {
    return this.reProjectsKpiBudget.updateRisk(id, riskId, body);
  }

  @Delete(':id/risks/:riskId')
  @UseGuards(StaffReProjectsRisksDeleteGuard)
  deleteRisk(
    @Param('id', ParseIntPipe) id: number,
    @Param('riskId', ParseIntPipe) riskId: number,
  ) {
    return this.reProjectsKpiBudget.deleteRisk(id, riskId);
  }

  @Get(':id/budget')
  @UseGuards(StaffReProjectsBudgetViewGuard)
  listBudget(@Param('id', ParseIntPipe) id: number) {
    return this.reProjectsKpiBudget.listBudget(id);
  }

  @Post(':id/budget')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffReProjectsBudgetWriteGuard)
  createBudgetLine(@Param('id', ParseIntPipe) id: number, @Body() body: SaveBudgetLineBody) {
    return this.reProjectsKpiBudget.createBudgetLine(id, body);
  }

  @Put(':id/budget/:lineId')
  @UseGuards(StaffReProjectsBudgetWriteGuard)
  updateBudgetLine(
    @Param('id', ParseIntPipe) id: number,
    @Param('lineId', ParseIntPipe) lineId: number,
    @Body() body: SaveBudgetLineBody,
  ) {
    return this.reProjectsKpiBudget.updateBudgetLine(id, lineId, body);
  }

  @Delete(':id/budget/:lineId')
  @UseGuards(StaffReProjectsBudgetDeleteGuard)
  deleteBudgetLine(
    @Param('id', ParseIntPipe) id: number,
    @Param('lineId', ParseIntPipe) lineId: number,
  ) {
    return this.reProjectsKpiBudget.deleteBudgetLine(id, lineId);
  }

  @Get(':id/summary')
  @UseGuards(StaffReProjectsViewGuard)
  projectSummary(@Param('id', ParseIntPipe) id: number) {
    return this.reProjects.projectSummary(id);
  }

  @Get(':id/products')
  @UseGuards(StaffReProjectsProductsViewGuard)
  listProducts(@Param('id', ParseIntPipe) id: number) {
    return this.reProjects.listProducts(id);
  }

  @Post(':id/products')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffReProjectsProductsWriteGuard)
  createProduct(@Param('id', ParseIntPipe) id: number, @Body() body: SaveProductBody) {
    return this.reProjects.createProduct(id, body);
  }

  @Put(':id/products/:productId')
  @UseGuards(StaffReProjectsProductsWriteGuard)
  updateProduct(
    @Param('id', ParseIntPipe) id: number,
    @Param('productId', ParseIntPipe) productId: number,
    @Body() body: SaveProductBody,
  ) {
    return this.reProjects.updateProduct(id, productId, body);
  }

  @Delete(':id/products/:productId')
  @UseGuards(StaffReProjectsProductsDeleteGuard)
  deleteProduct(
    @Param('id', ParseIntPipe) id: number,
    @Param('productId', ParseIntPipe) productId: number,
  ) {
    return this.reProjects.deleteProduct(id, productId);
  }

  @Get(':id/zones')
  @UseGuards(StaffReProjectsViewGuard)
  listZones(@Param('id', ParseIntPipe) id: number) {
    return this.reProjects.listZones(id);
  }

  @Get(':id/inventory-by-zone')
  @UseGuards(StaffReProjectsProductsViewGuard)
  inventoryByZone(@Param('id', ParseIntPipe) id: number) {
    return this.reProjects.inventoryByZone(id);
  }

  @Get(':id/price-batches')
  @UseGuards(StaffReProjectsProductsViewGuard)
  priceBatches(@Param('id', ParseIntPipe) id: number) {
    return this.reProjects.priceBatches(id);
  }

  @Get(':id/price-lists')
  @UseGuards(StaffReProjectsProductsViewGuard)
  listPriceLists(@Param('id', ParseIntPipe) id: number) {
    return this.reProjects.listPriceLists(id);
  }

  @Post(':id/price-lists')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffReProjectsProductsWriteGuard)
  createPriceList(@Param('id', ParseIntPipe) id: number, @Body() body: SavePriceListBody) {
    return this.reProjects.createPriceList(id, body);
  }

  @Get(':id/price-lists/:listId')
  @UseGuards(StaffReProjectsProductsViewGuard)
  getPriceList(
    @Param('id', ParseIntPipe) id: number,
    @Param('listId', ParseIntPipe) listId: number,
  ) {
    return this.reProjects.getPriceList(id, listId);
  }

  @Put(':id/price-lists/:listId')
  @UseGuards(StaffReProjectsProductsWriteGuard)
  updatePriceList(
    @Param('id', ParseIntPipe) id: number,
    @Param('listId', ParseIntPipe) listId: number,
    @Body() body: SavePriceListBody,
  ) {
    return this.reProjects.updatePriceList(id, listId, body);
  }

  @Delete(':id/price-lists/:listId')
  @UseGuards(StaffReProjectsProductsDeleteGuard)
  deletePriceList(
    @Param('id', ParseIntPipe) id: number,
    @Param('listId', ParseIntPipe) listId: number,
  ) {
    return this.reProjects.deletePriceList(id, listId);
  }

  @Get(':id/accounting/dashboard')
  @UseGuards(StaffReProjectsBudgetViewGuard)
  accountingDashboard(@Param('id', ParseIntPipe) id: number) {
    return this.reProjectsAccounting.dashboard(id);
  }

  @Get(':id/accounting/cash-flow')
  @UseGuards(StaffReProjectsBudgetViewGuard)
  listAccountingCashFlow(
    @Param('id', ParseIntPipe) id: number,
    @Query('flow_type') flowType?: string,
    @Query('category') category?: string,
    @Query('status') status?: string,
  ) {
    return this.reProjectsAccounting.listCashFlow(id, {
      flow_type: flowType?.trim() || undefined,
      category: category?.trim() || undefined,
      status: status?.trim() || undefined,
    });
  }

  @Post(':id/accounting/cash-flow')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffReProjectsBudgetWriteGuard)
  createAccountingCashFlow(@Param('id', ParseIntPipe) id: number, @Body() body: SaveCashFlowBody) {
    return this.reProjectsAccounting.createCashFlow(id, body);
  }

  @Put(':id/accounting/cash-flow/:lineId')
  @UseGuards(StaffReProjectsBudgetWriteGuard)
  updateAccountingCashFlow(
    @Param('id', ParseIntPipe) id: number,
    @Param('lineId', ParseIntPipe) lineId: number,
    @Body() body: SaveCashFlowBody,
  ) {
    return this.reProjectsAccounting.updateCashFlow(id, lineId, body);
  }

  @Delete(':id/accounting/cash-flow/:lineId')
  @UseGuards(StaffReProjectsBudgetDeleteGuard)
  deleteAccountingCashFlow(
    @Param('id', ParseIntPipe) id: number,
    @Param('lineId', ParseIntPipe) lineId: number,
  ) {
    return this.reProjectsAccounting.removeCashFlow(id, lineId);
  }

  @Post(':id/accounting/cash-flow/import')
  @UseGuards(StaffReProjectsBudgetWriteGuard)
  importAccountingCashFlow(@Param('id', ParseIntPipe) id: number, @Body() body: ImportCashFlowBody) {
    return this.reProjectsAccounting.importCashFlow(id, body);
  }

  @Post(':id/accounting/sync-from-plans')
  @UseGuards(StaffReProjectsBudgetWriteGuard)
  syncAccountingFromPlans(@Param('id', ParseIntPipe) id: number) {
    return this.reProjectsAccounting.syncFromPlans(id);
  }

  @Post(':id/accounting/sync-inventory-revenue')
  @UseGuards(StaffReProjectsBudgetWriteGuard)
  syncAccountingInventoryRevenue(@Param('id', ParseIntPipe) id: number) {
    return this.reProjectsAccounting.syncInventoryRevenue(id);
  }

  @Post(':id/accounting/ai/ask')
  @UseGuards(StaffReProjectsBudgetViewGuard)
  accountingAiAsk(@Param('id', ParseIntPipe) id: number, @Body() body: AccountingAiAskBody) {
    return this.reProjectsAccounting.aiAsk(id, body);
  }

  @Get(':id/accounting/export')
  @UseGuards(StaffReProjectsBudgetExportGuard)
  accountingExport(@Param('id', ParseIntPipe) id: number) {
    return this.reProjectsAccounting.exportBundle(id);
  }

  @Get(':id/accounting/risk-predictions')
  @UseGuards(StaffReProjectsBudgetViewGuard)
  accountingRiskPredictions(@Param('id', ParseIntPipe) id: number) {
    return this.reProjectsAccounting.riskPredictions(id);
  }

  @Get(':id/accounting/forecast')
  @UseGuards(StaffReProjectsBudgetViewGuard)
  accountingForecast(
    @Param('id', ParseIntPipe) id: number,
    @Query('months_ahead') monthsAhead?: string,
    @Query('months') months?: string,
  ) {
    return this.reProjectsAccounting.forecast(id, monthsAhead ?? months);
  }

  @Post(':id/accounting/risk-predictions/apply')
  @UseGuards(StaffReProjectsBudgetWriteGuard)
  applyAccountingRiskPredictions(
    @Param('id', ParseIntPipe) id: number,
    @Body() body: ApplyPredictedRisksBody,
  ) {
    return this.reProjectsAccounting.applyRiskPredictions(id, body);
  }

  @Get(':id/staff')
  @UseGuards(StaffReProjectsViewGuard)
  listStaff(@Param('id', ParseIntPipe) id: number) {
    return this.reProjectsOps.listStaff(id);
  }

  @Post(':id/staff')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffReProjectsWriteGuard)
  addStaff(@Param('id', ParseIntPipe) id: number, @Body() body: AddProjectStaffBody) {
    return this.reProjectsOps.addStaff(id, body);
  }

  @Put(':id/staff/:staffId')
  @UseGuards(StaffReProjectsWriteGuard)
  updateStaff(
    @Param('id', ParseIntPipe) id: number,
    @Param('staffId', ParseIntPipe) staffId: number,
    @Body() body: UpdateProjectStaffBody,
  ) {
    return this.reProjectsOps.updateStaff(id, staffId, body);
  }

  @Delete(':id/staff/:staffId')
  @UseGuards(StaffReProjectsWriteGuard)
  removeStaff(
    @Param('id', ParseIntPipe) id: number,
    @Param('staffId', ParseIntPipe) staffId: number,
  ) {
    return this.reProjectsOps.removeStaff(id, staffId);
  }

  @Get(':id/lead-config')
  @UseGuards(StaffReProjectsViewGuard)
  getLeadConfig(@Param('id', ParseIntPipe) id: number) {
    return this.reProjectsOps.getLeadConfig(id);
  }

  @Put(':id/lead-config')
  @UseGuards(StaffReProjectsWriteGuard)
  saveLeadConfig(@Param('id', ParseIntPipe) id: number, @Body() body: SaveProjectLeadConfigBody) {
    return this.reProjectsOps.saveLeadConfig(id, body);
  }

  @Post(':id/webhook-test')
  @UseGuards(StaffReProjectsWriteGuard)
  webhookTest(@Param('id', ParseIntPipe) id: number) {
    return this.reProjectsOps.webhookTest(id);
  }

  @Get(':id/workflow')
  @UseGuards(StaffReProjectsViewGuard)
  projectWorkflow(@Param('id', ParseIntPipe) id: number) {
    return this.reProjectsOps.workflow(id);
  }

  @Get(':id/export')
  @UseGuards(StaffReProjectsExportGuard)
  exportProject(
    @Param('id', ParseIntPipe) id: number,
    @Query('report') report?: string,
    @Query('format') _format?: string,
  ) {
    return this.reProjectsOps.exportBundle(id, report);
  }

  @Get(':id')
  @UseGuards(StaffReProjectsViewGuard)
  getProject(@Param('id', ParseIntPipe) id: number) {
    return this.reProjects.getProject(id);
  }

  @Put(':id')
  @UseGuards(StaffReProjectsUpdateGuard)
  updateProject(@Param('id', ParseIntPipe) id: number, @Body() body: CreateReProjectBody) {
    return this.reProjects.updateProject(id, body);
  }

  @Delete(':id')
  @UseGuards(StaffReProjectsDeleteGuard)
  deleteProject(@Param('id', ParseIntPipe) id: number) {
    return this.reProjects.deleteProject(id);
  }
}
