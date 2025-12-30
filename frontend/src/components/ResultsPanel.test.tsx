import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { type ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { JobType, type BootstrapSingleResults, type DescriptiveOnlyResults } from "../api";
import { ResultsPanel } from "./ResultsPanel";

const baseProps = {
  jobId: "job-123",
  isLoading: false,
  isError: false,
  artifacts: [],
  onDownloadArtifact: vi.fn(),
  loadPlot: vi.fn().mockResolvedValue({})
};

const createWrapper = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
};

const wrapper = createWrapper();

describe("ResultsPanel interpretation section", () => {
  it("renders markdown interpretation content", async () => {
    const results: BootstrapSingleResults = {
      jobId: "job-123",
      jobType: JobType.BOOTSTRAP_SINGLE,
      decision: { alpha: 0.05, pValue: 0.01, significant: true },
      metrics: {},
      descriptive: {},
      plots: [],
      interpretation: { text: "## Insights\n- First takeaway" }
    };

    render(<ResultsPanel {...baseProps} results={results} />, { wrapper });

    await userEvent.click(screen.getByRole("button", { name: /interpretation/i }));
    const panel = await screen.findByTestId("interpretation-panel");

    expect(within(panel).getByRole("heading", { name: /insights/i })).toBeInTheDocument();
    expect(within(panel).getByText(/first takeaway/i)).toBeInTheDocument();
  });

  it("shows placeholder when no interpretation is available", async () => {
    const results: DescriptiveOnlyResults = {
      jobId: "job-234",
      jobType: JobType.DESCRIPTIVE_ONLY,
      descriptive: { mean: 12.3 },
      plots: []
    };

    render(<ResultsPanel {...baseProps} results={results} />, { wrapper });

    await userEvent.click(screen.getByRole("button", { name: /interpretation/i }));

    expect(await screen.findByText(/No interpretation available for this job/i)).toBeVisible();
  });

  it("parses stringified JSON interpretation safely", async () => {
    const results: BootstrapSingleResults = {
      jobId: "job-345",
      jobType: JobType.BOOTSTRAP_SINGLE,
      decision: { alpha: 0.05, pValue: 0.05, significant: false },
      metrics: {},
      descriptive: {},
      plots: [],
      interpretation: '{"text":"## Title\\\\n- Bullet point"}'
    };

    render(<ResultsPanel {...baseProps} results={results} />, { wrapper });

    await userEvent.click(screen.getByRole("button", { name: /interpretation/i }));
    const panel = await screen.findByTestId("interpretation-panel");

    expect(within(panel).getByRole("heading", { name: /title/i })).toBeInTheDocument();
    expect(within(panel).getByText(/bullet point/i)).toBeInTheDocument();
  });
});
