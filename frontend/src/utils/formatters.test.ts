import { describe, expect, it } from "vitest";

import { formatTableNumber, formatTableValue, humanizeMetricKey } from "./formatters";

describe("formatTableNumber", () => {
  it("formats floats with one decimal place", () => {
    expect(formatTableNumber(12.34)).toBe("12.3");
  });

  it("formats integers consistently with one decimal place", () => {
    expect(formatTableNumber(12)).toBe("12.0");
  });

  it("returns placeholder for NaN", () => {
    expect(formatTableNumber(Number.NaN)).toBe("—");
  });

  it("returns placeholder for nullish values", () => {
    expect(formatTableNumber(null)).toBe("—");
    expect(formatTableNumber(undefined)).toBe("—");
  });
});

describe("humanizeMetricKey", () => {
  it("uses predefined mapping when available", () => {
    expect(humanizeMetricKey("p50")).toBe("Median (P50)");
    expect(humanizeMetricKey("std")).toBe("Std dev");
  });

  it("falls back to title case for unknown metrics", () => {
    expect(humanizeMetricKey("ci_width")).toBe("Ci Width");
    expect(humanizeMetricKey("customMetricKey")).toBe("Custom Metric Key");
  });
});

describe("formatTableValue", () => {
  it("formats numeric string input to one decimal place", () => {
    expect(formatTableValue("15.66")).toBe("15.7");
  });

  it("stringifies objects safely", () => {
    expect(formatTableValue({ x: 1 })).toBe(JSON.stringify({ x: 1 }));
  });
});
