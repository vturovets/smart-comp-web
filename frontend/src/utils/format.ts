export const metricTitleMap: Record<string, string> = {
  p50: "Median (P50)",
  median: "Median (P50)",
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

const toWords = (key: string): string[] =>
  key
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/[_-]+/g, " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean);

export const humanizeMetric = (key: string): string => {
  const normalizedKey = key?.trim();
  if (!normalizedKey) return "—";

  const mapped = metricTitleMap[normalizedKey.toLowerCase()];
  if (mapped) return mapped;

  const words = toWords(normalizedKey);
  if (!words.length) return "—";

  return words.map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join(" ");
};

export const formatNumber1dp = (value: unknown): string => {
  if (value === null || value === undefined) return "—";

  const numericValue =
    typeof value === "number"
      ? value
      : typeof value === "string" && value.trim() !== ""
        ? Number(value)
        : Number.NaN;

  if (!Number.isFinite(numericValue)) return "—";

  return numericValue.toFixed(1);
};

export const formatValueForDisplay = (value: unknown): string => {
  if (value === null || value === undefined) return "—";

  if (typeof value === "number") {
    return formatNumber1dp(value);
  }

  if (typeof value === "string") {
    if (!value.trim()) return "—";

    const numericValue = Number(value);
    if (Number.isFinite(numericValue)) return formatNumber1dp(numericValue);

    return value;
  }

  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return "—";
    }
  }

  return String(value);
};
