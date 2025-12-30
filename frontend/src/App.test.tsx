import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import App from "./App";
import { JobStatus, JobType } from "./api";

const defaults = {
  alpha: 0.05,
  descriptiveEnabled: true,
  createLog: false,
  cleanAll: false,
  plots: {}
};

const mockResults = {
  jobId: "job-1",
  jobType: JobType.BOOTSTRAP_SINGLE,
  decision: { alpha: 0.05, pValue: 0.03, significant: true },
  metrics: { delta: 1.2 },
  descriptive: { mean: 12.3 },
  plots: [{ artifactName: "plot.json", kind: "histogram" }]
};

const mockArtifacts = {
  jobId: "job-1",
  artifacts: [
    { name: "plot.json", contentType: "application/json", sizeBytes: 1200, createdAt: new Date().toISOString() },
    { name: "results.json", contentType: "application/json", sizeBytes: 800, createdAt: new Date().toISOString() }
  ]
};

const mockApi = {
  getConfigDefaults: vi.fn().mockResolvedValue(defaults),
  createJob: vi.fn().mockResolvedValue({ jobId: "job-1" }),
  getJob: vi.fn().mockResolvedValue({
    jobId: "job-1",
    jobType: JobType.BOOTSTRAP_SINGLE,
    status: JobStatus.COMPLETED,
    createdAt: new Date().toISOString(),
    progress: { percent: 100 }
  }),
  getResults: vi.fn().mockResolvedValue(mockResults),
  listArtifacts: vi.fn().mockResolvedValue(mockArtifacts),
  downloadArtifactWithInfo: vi.fn().mockResolvedValue({
    blob: new Blob([JSON.stringify({ data: [{ x: [1, 2], y: [3, 4] }] })], { type: "application/json" }),
    contentType: "application/json"
  }),
  downloadArtifact: vi.fn().mockResolvedValue(new Blob()),
  cancelJob: vi.fn().mockResolvedValue(undefined)
};

vi.mock("./api", async () => {
  const actual = await vi.importActual<typeof import("./api")>("./api");
  return {
    ...actual,
    buildApiClient: () => mockApi
  };
});

const createWrapper = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
};

describe("App", () => {
  it("runs a happy path job flow", async () => {
    render(<App />, { wrapper: createWrapper() });
    expect(await screen.findByText(/analysis console/i)).toBeVisible();

    const file = new File(["a,b,c"], "data.csv", { type: "text/csv" });
    const fileInput = screen.getByTestId("file1-input") as HTMLInputElement;
    await userEvent.upload(fileInput, file);

    await userEvent.click(screen.getByRole("button", { name: /start job/i }));

    await waitFor(() => expect(mockApi.createJob).toHaveBeenCalled());
    await waitFor(() => expect(mockApi.getJob).toHaveBeenCalled());
    expect(await screen.findByText(/completed/i)).toBeVisible();
    expect(await screen.findByText(/delta/i)).toBeVisible();
    expect(await screen.findByText(/Artifacts/i)).toBeVisible();
    expect(mockApi.createJob).toHaveBeenCalled();
  }, 10000);
});
