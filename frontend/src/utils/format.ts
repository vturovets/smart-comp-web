export interface FormatFloatOptions {
  isAlpha?: boolean;
}

export const formatFloat = (value: number, { isAlpha = false }: FormatFloatOptions = {}): string => {
  if (!Number.isFinite(value)) return String(value);

  const digits = isAlpha ? 2 : 1;
  return value.toFixed(digits);
};

export const formatDisplayValue = (value: unknown, key?: string): string => {
  if (value === null || value === undefined) {
    return "—";
  }

  if (typeof value === "number") {
    return formatFloat(value, { isAlpha: key?.toLowerCase() === "alpha" });
  }

  if (typeof value === "object") {
    return JSON.stringify(value);
  }

  return String(value);
};
