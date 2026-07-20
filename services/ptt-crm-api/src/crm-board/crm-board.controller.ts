import { Controller, Get, Req, UseGuards } from '@nestjs/common';
import { Request } from 'express';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { StaffJwtPayload } from '../staff-auth/staff-jwt.util';
import { CrmBoardService } from './crm-board.service';
import { StaffCrmBoardViewGuard } from './guards/staff-crm-board.guard';

@Controller('api/crm')
@UseGuards(StaffOrInternalKeyGuard, StaffCrmBoardViewGuard)
export class CrmBoardController {
  constructor(private readonly crmBoard: CrmBoardService) {}

  @Get('board')
  board(@Req() req: Request & { staffUser: StaffJwtPayload }) {
    return this.crmBoard.board(req.staffUser);
  }
}
