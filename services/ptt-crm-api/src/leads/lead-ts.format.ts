export function formatLeadTs(value: unknown): string {
  if (value == null) {
    return '';
  }
  if (value instanceof Date) {
    if (
      value.getUTCHours() === 0 &&
      value.getUTCMinutes() === 0 &&
      value.getUTCSeconds() === 0 &&
      value.getUTCMilliseconds() === 0
    ) {
      return value.toISOString().slice(0, 10);
    }
    const text = value.toISOString();
    return text.endsWith('Z') ? text : text.replace('+00:00', 'Z');
  }
  return String(value);
}
