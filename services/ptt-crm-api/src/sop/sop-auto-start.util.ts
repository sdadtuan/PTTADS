/** lifecycle_once: reuse existing SOP run when lifecycle already linked and run exists. */
export function shouldReuseLifecycleSopRun(
  existingRunId: number | null | undefined,
  existingRunValid: boolean,
): boolean {
  return !!(existingRunId && existingRunId > 0 && existingRunValid);
}
