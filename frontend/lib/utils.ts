export function cn(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

export function formatCurrency(value: number | null | undefined) {
  if (value === null || value === undefined) return "Price on request";
  return `RM ${value.toLocaleString()}`;
}

export function titleCase(value: string | null | undefined) {
  if (!value) return "Unknown";
  return value
    .replace(/_/g, " ")
    .split(" ")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function toQueryString(data: Record<string, unknown>) {
  const params = new URLSearchParams();

  for (const [key, value] of Object.entries(data)) {
    if (value === null || value === undefined || value === "") continue;
    params.set(key, String(value));
  }

  return params.toString();
}
