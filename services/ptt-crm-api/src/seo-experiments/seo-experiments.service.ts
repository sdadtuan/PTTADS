import { Injectable } from '@nestjs/common';
import { experimentsEnabled } from './seo-experiments.constants';
import { SeoExperimentsRepository } from './seo-experiments.repository';
import { SeoExperimentObservationRow, SeoExperimentRow } from './seo-experiments.types';

@Injectable()
export class SeoExperimentsService {
  constructor(private readonly repo: SeoExperimentsRepository) {}

  status(): { ok: boolean; enabled: boolean } {
    return { ok: true, enabled: experimentsEnabled() };
  }

  listExperiments(customerId: number): Promise<SeoExperimentRow[]> {
    return this.repo.listExperiments(customerId);
  }

  async getExperiment(experimentId: number) {
    const experiment = await this.repo.getExperiment(experimentId);
    if (!experiment) return { ok: false, error: 'experiment_not_found' };
    const observations = await this.repo.listObservations(experimentId);
    return { ok: true, experiment, observations };
  }

  createExperiment(customerId: number, body: Record<string, unknown>): Promise<{ ok: boolean; experiment: SeoExperimentRow }> {
    return this.repo.createExperiment(customerId, body).then((experiment) => ({ ok: true, experiment }));
  }

  updateStatus(experimentId: number, status: string): Promise<{ ok: boolean; experiment: SeoExperimentRow }> {
    return this.repo.updateStatus(experimentId, status).then((experiment) => ({ ok: true, experiment }));
  }

  addObservation(
    experimentId: number,
    body: Record<string, unknown>,
  ): Promise<{ ok: boolean; observation: SeoExperimentObservationRow }> {
    return this.repo.addObservation(experimentId, body).then((observation) => ({ ok: true, observation }));
  }
}
