import { describe, expect, it } from "vitest";

import { formatNumber1dp, formatValueForDisplay, humanizeMetric, metricTitleMap } from "./format";

describe("formatNumber1dp", () => {
  it("formats floats with one decimal place", () => {
    expect(formatNumber1dp(12.345)).toBe("12.3");
  });

  it("formats integers with one decimal place", () => {
    expect(formatNumber1dp(12)).toBe("12.0");
  });

  it("returns placeholder for null-like values", () => {
    expect(formatNumber1dp(null)).toBe("—");
    expect(formatNumber1dp(undefined)).toBe("—");
    expect(formatNumber1dp(Number.NaN)).toBe("—");
  });

  it("parses numeric strings", () => {
    expect(formatNumber1dp("15.99")).toBe("16.0");
  });
});

describe("humanizeMetric", () => {
  it("uses explicit mappings when available", () => {
    expect(humanizeMetric("p95")).toBe(metricTitleMap.p95);
    expect(humanizeMetric("P50")).toBe(metricTitleMap.p50);
  });

  it("title-cases unknown metric keys", () => {
    expect(humanizeMetric("conversion_rate")).toBe("Conversion Rate");
    expect(humanizeMetric("liftDelta")).toBe("Lift Delta");
  });

  it("handles empty or whitespace-only keys", () => {
    expect(humanizeMetric("")).toBe("—");
    expect(humanizeMetric("   ")).toBe("—");
  });
});

describe("formatValueForDisplay", () => {
  it("formats numbers and numeric strings to one decimal place", () => {
    expect(formatValueForDisplay(10)).toBe("10.0");
    expect(formatValueForDisplay("10.22")).toBe("10.2");
  });

  it("returns placeholder for null-like or non-finite numbers", () => {
    expect(formatValueForDisplay(null)).toBe("—");
    expect(formatValueForDisplay(undefined)).toBe("—");
    expect(formatValueForDisplay(Number.NaN)).toBe("—");
  });

  it("stringifies objects safely", () => {
    expect(formatValueForDisplay({ a: 1 })).toBe("{\"a\":1}");
  });
});
