import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(null, { status: 200 })) as unknown as typeof fetch
  );
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});
