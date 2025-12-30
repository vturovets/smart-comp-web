import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { setupServer } from "msw/node";
import { beforeAll, afterAll, afterEach, describe, expect, it } from "vitest";

import App from "../../src/App";
import { JobStatus, JobType } from "../../src/api";

const defaults = {
  alpha: 0.05,
  descriptiveEnabled: true,
  createLog: false,
  cleanAll: false,
  plots: {}
};

const kwResults = {
  jobId: "e2e-1",
  jobType: JobType.KW_PERMUTATION,
  decision: { alpha: 0.05, pValue: 0.07 },
  omnibus: { hStatistic: 5.1, permutations: 200 },
  groups: [
    { groupName: "A", files: [{ fileName: "a.csv", n: 10, median: 1.2, p95: 2.5 }] },
    { groupName: "B", files: [{ fileName: "b.csv", n: 9, median: 1.4, p95: 2.8 }] }
  ],
  plots: [{ artifactName: "plot.json", kind: "boxplot" }]
};

const kwArtifacts = {
  jobId: "e2e-1",
  artifacts: [{ name: "plot.json", sizeBytes: 1000, createdAt: new Date().toISOString(), contentType: "application/json" }]
};

const server = setupServer(
  http.get("http://localhost:8000/api/config/defaults", () => HttpResponse.json(defaults)),
  http.post("http://localhost:8000/api/jobs", () => HttpResponse.json({ jobId: "e2e-1" })),
  http.get("http://localhost:8000/api/jobs/e2e-1", () =>
    HttpResponse.json({
      jobId: "e2e-1",
      jobType: JobType.KW_PERMUTATION,
      status: JobStatus.COMPLETED,
      createdAt: new Date().toISOString(),
      progress: { percent: 100 }
    })
  ),
  http.get("http://localhost:8000/api/jobs/e2e-1/results", () => HttpResponse.json(kwResults)),
  http.get("http://localhost:8000/api/jobs/e2e-1/artifacts", () => HttpResponse.json(kwArtifacts)),
  http.get("http://localhost:8000/api/jobs/e2e-1/artifacts/plot.json", () =>
    HttpResponse.json({ data: [{ x: [1, 2], y: [3, 4], type: "box" }] })
  )
);

const createWrapper = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
};

describe("happy path UI e2e (mocked provider)", () => {
  beforeAll(() => server.listen());
  afterEach(() => server.resetHandlers());
  afterAll(() => server.close());

  it("walks through KW permutation flow", async () => {
    render(<App />, { wrapper: createWrapper() });
    expect(await screen.findByText(/Analysis console/i)).toBeVisible();

    await userEvent.click(screen.getByLabelText(/job type/i));
    await userEvent.click(screen.getByRole("option", { name: /kw permutation/i }));
    expect(screen.getByTestId("kw-helper")).toBeVisible();

    const fileInput = screen.getByTestId("files-input") as HTMLInputElement;
    const files = [
      new File(["a"], "group-a.csv", { type: "text/csv" }),
      new File(["b"], "group-b.csv", { type: "text/csv" }),
      new File(["c"], "group-c.csv", { type: "text/csv" })
    ];
    await userEvent.upload(fileInput, files);

    await userEvent.click(screen.getByRole("button", { name: /start job/i }));
    await waitFor(() => expect(screen.getByText(/completed/i)).toBeInTheDocument());
    expect(await screen.findByText(/Group details/i)).toBeVisible();
    expect(await screen.findByText(/Artifacts/i)).toBeVisible();
  });
});
