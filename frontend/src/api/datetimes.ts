/** SQLite API timestamps without an offset represent UTC, never browser-local time. */
export function utcTimestamp(value: string): string {
  return /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(value) ? `${value}Z` : value
}
