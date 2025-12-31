const metricDisplayNames: Record<string, string> = {
  p50: "Median (P50)",
  p90: "P90",
  p95: "P95",
  p99: "P99",
  mean: "Mean",
  std: "Std dev",
  min: "Min",
  max: "Max",
  moe: "Margin of error",
  ci_low: "CI low",
  ci_high: "CI high",
  n: "Sample size"
};

const titleCase = (value: string): string =>
  value
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/[_-]+/g, " ")
    .split(" ")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");

export const humanizeMetricKey = (key: string): string => {
  const normalizedKey = key.toString();
  const mapped = metricDisplayNames[normalizedKey.toLowerCase()];
  if (mapped) return mapped;
  return titleCase(normalizedKey);
};

export const formatTableNumber = (value: unknown): string => {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") {
    if (Number.isNaN(value)) return "—";
    return value.toFixed(1);
  }

  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed) return "—";
    const numeric = Number(trimmed);
    if (!Number.isNaN(numeric)) {
      return numeric.toFixed(1);
    }
    if (trimmed.toLowerCase() === "nan") return "—";
    return value;
  }

  return String(value);
};

export const formatTableValue = (value: unknown): string => {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number" || typeof value === "string") return formatTableNumber(value);
  if (typeof value === "boolean") return value ? "True" : "False";
  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
};

export const metricTitles = metricDisplayNames;
