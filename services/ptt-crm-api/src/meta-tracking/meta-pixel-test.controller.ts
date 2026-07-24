import { Controller, Param, Post, UseGuards } from '@nestjs/common';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import {
  StaffMetaTrackingConfigureGuard,
  StaffMetaTrackingEnabledGuard,
  StaffMetaTrackingViewGuard,
} from './guards/staff-meta-tracking.guard';
import { MetaPixelTestService } from './meta-pixel-test.service';
import { TestPixelResponse } from './meta-tracking.types';

@Controller('api/v1/clients')
export class MetaPixelTestController {
  constructor(private readonly pixelTest: MetaPixelTestService) {}

  @Post(':clientId/channel-accounts/:accountId/test-pixel')
  @UseGuards(
    StaffOrInternalKeyGuard,
    StaffMetaTrackingEnabledGuard,
    StaffMetaTrackingViewGuard,
    StaffMetaTrackingConfigureGuard,
  )
  testPixel(
    @Param('clientId') clientId: string,
    @Param('accountId') accountId: string,
  ): Promise<TestPixelResponse> {
    return this.pixelTest.testPixel(clientId, accountId);
  }
}
