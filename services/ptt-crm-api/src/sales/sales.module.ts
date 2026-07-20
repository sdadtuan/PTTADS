import { Module } from '@nestjs/common';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import {
  StaffSalesFunnelViewGuard,
  StaffSalesMarketWriteGuard,
  StaffSalesPartnerWriteGuard,
  StaffSalesTrainingWriteGuard,
  StaffSalesViewGuard,
  StaffSalesWriteGuard,
} from './guards/staff-sales.guard';
import { SalesController } from './sales.controller';
import { SalesSqliteRepository } from './sales-sqlite.repository';
import { SalesService } from './sales.service';

@Module({
  imports: [StaffAuthModule],
  controllers: [SalesController],
  providers: [
    SalesService,
    SalesSqliteRepository,
    StaffSalesViewGuard,
    StaffSalesFunnelViewGuard,
    StaffSalesWriteGuard,
    StaffSalesPartnerWriteGuard,
    StaffSalesTrainingWriteGuard,
    StaffSalesMarketWriteGuard,
  ],
  exports: [SalesService],
})
export class SalesModule {}
