export function formatDate(value: unknown, timezone = "America/New_York"): string {
  if (!value) return "Unknown";
  if (/^\d{4}-\d{2}-\d{2}$/.test(String(value))) {
    const [year, month, day] = String(value).split("-").map(Number);
    return new Intl.DateTimeFormat("en-US", {month: "short", day: "numeric", year: "numeric", timeZone: "UTC"}).format(new Date(Date.UTC(year, month - 1, day)));
  }
  const date = new Date(String(value));
  if (Number.isNaN(date.valueOf())) return String(value);
  return new Intl.DateTimeFormat("en-US", {month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit", timeZone: timezone, timeZoneName: "short"}).format(date);
}

export function formatNumber(value: unknown, kind: "count" | "decimal" | "percent" | "currency" = "count"): string {
  if (value === null || value === undefined || value === "") return "Unknown";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return String(value);
  if (kind === "count") return new Intl.NumberFormat("en-US", {maximumFractionDigits: 0}).format(numeric);
  if (kind === "percent") return new Intl.NumberFormat("en-US", {style: "percent", maximumFractionDigits: 1}).format(numeric);
  if (kind === "currency") return new Intl.NumberFormat("en-US", {style: "currency", currency: "USD"}).format(numeric);
  return new Intl.NumberFormat("en-US", {maximumFractionDigits: 4}).format(numeric);
}

export function humanize(value: string): string { return value.replaceAll("_", " ").toLowerCase().replace(/^./, (letter) => letter.toUpperCase()); }
