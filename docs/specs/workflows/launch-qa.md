# Launch QA Workflow (Phase 3 T3)

- **Type:** `LaunchQAWorkflow`
- **ID:** `launch-qa-{run_id}`
- **Table:** `launch_qa_runs`
- **Start:** `POST /api/v1/workflows/launch-qa/start`
- **Checklist:** 6 items (pixel, naming, budget, creative, UTM, QA sign-off)
- **Pass:** Sets `launch_ready=true`, `status=passed` when all items checked
