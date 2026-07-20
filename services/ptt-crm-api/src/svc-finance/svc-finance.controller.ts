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
import {
  StaffSvcFinanceViewGuard,
  StaffSvcFinanceWriteGuard,
} from './guards/staff-svc-finance.guard';
import { SvcFinanceService } from './svc-finance.service';

@Controller('api/crm')
@UseGuards(StaffOrInternalKeyGuard)
export class SvcFinanceController {
  constructor(private readonly svcFinance: SvcFinanceService) {}

  @Get('svc-finance/:lifecycleId/summary')
  @UseGuards(StaffSvcFinanceViewGuard)
  summary(@Param('lifecycleId', ParseIntPipe) lifecycleId: number) {
    return this.svcFinance.summary(lifecycleId);
  }

  @Post('svc-payments')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffSvcFinanceWriteGuard)
  createPayment(@Body() body: Record<string, unknown>) {
    return this.svcFinance.createPayment(body);
  }

  @Patch('svc-payments/:paymentId')
  @UseGuards(StaffSvcFinanceWriteGuard)
  patchPayment(
    @Param('paymentId', ParseIntPipe) paymentId: number,
    @Body() body: Record<string, unknown>,
  ) {
    return this.svcFinance.patchPayment(paymentId, body);
  }

  @Delete('svc-payments/:paymentId')
  @UseGuards(StaffSvcFinanceWriteGuard)
  deletePayment(@Param('paymentId', ParseIntPipe) paymentId: number) {
    return this.svcFinance.deletePayment(paymentId);
  }
}
