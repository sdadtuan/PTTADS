# Client Onboarding Workflow (Phase 3 T2)

- **Type:** `ClientOnboardingWorkflow`
- **ID:** `client-onboarding-{client_id}`
- **Start:** `POST /api/v1/workflows/onboarding/start` (Nest internal) or Flask Agency button
- **Signal:** `checklist_updated` — auto nudge when AM ticks checklist (Flask PATCH → Nest nudge)
- **Complete:** Activity activates client when onboarding 100%
