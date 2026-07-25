export interface OnboardDeliverGateResult {
  ok: boolean;
  messages: string[];
  orchestrator_percent: number;
  checklist_percent: number;
  client_active: boolean;
}

/** PROD-P1-WIZ — block onboard→deliver when orchestrator/checklist incomplete. */
export function validateOnboardDeliverGate(input: {
  orchestratorRequiredPercent?: number;
  checklistPercent?: number;
  clientActive?: boolean;
}): OnboardDeliverGateResult {
  const orchestratorPercent = Math.max(0, Math.min(100, Number(input.orchestratorRequiredPercent ?? 0)));
  const checklistPercent = Math.max(0, Math.min(100, Number(input.checklistPercent ?? 0)));
  const clientActive = Boolean(input.clientActive);

  if (clientActive) {
    return {
      ok: true,
      messages: ['Agency client đã active — onboard coi như pass.'],
      orchestrator_percent: orchestratorPercent,
      checklist_percent: checklistPercent,
      client_active: true,
    };
  }

  const orchestratorOk = orchestratorPercent >= 100;
  const checklistOk = checklistPercent >= 100;
  const ok = orchestratorOk && checklistOk;
  const messages: string[] = [];
  if (!orchestratorOk) {
    messages.push(`Orchestrator onboard ${orchestratorPercent}% — cần 100% trước Deliver.`);
  }
  if (!checklistOk) {
    messages.push(`Checklist agency ${checklistPercent}% — cần 100% trước Deliver.`);
  }
  if (ok) {
    messages.push('Onboard orchestrator + checklist đạt 100%.');
  }

  return {
    ok,
    messages,
    orchestrator_percent: orchestratorPercent,
    checklist_percent: checklistPercent,
    client_active: false,
  };
}
