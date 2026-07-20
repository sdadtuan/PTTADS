import {
  Body,
  Controller,
  Get,
  HttpCode,
  HttpStatus,
  Post,
  Query,
  UseGuards,
} from '@nestjs/common';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import {
  StaffSalesFunnelViewGuard,
  StaffSalesMarketWriteGuard,
  StaffSalesPartnerWriteGuard,
  StaffSalesTrainingWriteGuard,
  StaffSalesViewGuard,
  StaffSalesWriteGuard,
} from './guards/staff-sales.guard';
import { SalesService } from './sales.service';
import {
  CreateMarketBody,
  CreatePartnerBody,
  CreateSalesPlanBody,
  CreateTrainingBody,
} from './sales.types';

@Controller('api/crm/sales')
@UseGuards(StaffOrInternalKeyGuard)
export class SalesController {
  constructor(private readonly sales: SalesService) {}

  @Get('summary')
  @UseGuards(StaffSalesViewGuard)
  summary() {
    return this.sales.summary();
  }

  @Get('plans')
  @UseGuards(StaffSalesViewGuard)
  listPlans() {
    return this.sales.listPlans();
  }

  @Post('plans')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffSalesViewGuard, StaffSalesWriteGuard)
  createPlan(@Body() body: CreateSalesPlanBody) {
    return this.sales.createPlan(body);
  }

  @Get('pipeline-cases')
  @UseGuards(StaffSalesFunnelViewGuard)
  pipelineCases(@Query('stage') stage?: string) {
    return this.sales.listPipelineCases(stage);
  }

  @Get('partners')
  @UseGuards(StaffSalesViewGuard)
  listPartners(@Query('q') q?: string) {
    return this.sales.listPartners(q);
  }

  @Post('partners')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffSalesViewGuard, StaffSalesPartnerWriteGuard)
  createPartner(@Body() body: CreatePartnerBody) {
    return this.sales.createPartner(body);
  }

  @Get('trainings')
  @UseGuards(StaffSalesViewGuard)
  listTrainings() {
    return this.sales.listTrainings();
  }

  @Post('trainings')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffSalesViewGuard, StaffSalesTrainingWriteGuard)
  createTraining(@Body() body: CreateTrainingBody) {
    return this.sales.createTraining(body);
  }

  @Get('market')
  @UseGuards(StaffSalesViewGuard)
  listMarket() {
    return this.sales.listMarket();
  }

  @Post('market')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffSalesViewGuard, StaffSalesMarketWriteGuard)
  createMarket(@Body() body: CreateMarketBody) {
    return this.sales.createMarket(body);
  }

  @Get('transactions')
  @UseGuards(StaffSalesViewGuard)
  listTransactions() {
    return this.sales.listTransactions();
  }

  @Get('reports')
  @UseGuards(StaffSalesViewGuard)
  reports() {
    return this.sales.salesReport();
  }
}
