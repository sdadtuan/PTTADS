import { Body, Controller, Get, Param, Post, UseGuards } from '@nestjs/common';
import { InternalKeyGuard } from '../auth/internal-key.guard';
import {
  StartLaunchQaBody,
  StartOnboardingBody,
  WorkflowsService,
} from './workflows.service';

@Controller('api/v1/workflows')
@UseGuards(InternalKeyGuard)
export class WorkflowsController {
  constructor(private readonly workflows: WorkflowsService) {}

  @Post('onboarding/start')
  startOnboarding(@Body() body: StartOnboardingBody) {
    return this.workflows.startOnboarding(body);
  }

  @Post('onboarding/:clientId/nudge')
  nudgeOnboarding(@Param('clientId') clientId: string) {
    return this.workflows.nudgeOnboarding(clientId);
  }

  @Post('launch-qa/start')
  startLaunchQa(@Body() body: StartLaunchQaBody) {
    return this.workflows.startLaunchQa(body);
  }

  @Post('launch-qa/:runId/nudge')
  nudgeLaunchQa(@Param('runId') runId: string) {
    return this.workflows.nudgeLaunchQa(runId);
  }

  @Get('onboarding/:clientId/status')
  onboardingStatus(@Param('clientId') clientId: string) {
    return this.workflows.onboardingStatus(clientId);
  }

  @Get('launch-qa/:runId/status')
  launchQaStatus(@Param('runId') runId: string) {
    return this.workflows.launchQaStatus(runId);
  }

  @Get('creative/:creativeId/status')
  creativeStatus(@Param('creativeId') creativeId: string) {
    return this.workflows.creativeStatus(creativeId);
  }
}
