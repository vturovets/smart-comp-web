import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { JobType } from "../api";
import { JobForm } from "./JobForm";

const defaults = {
  alpha: 0.05,
  descriptiveEnabled: true,
  createLog: false,
  cleanAll: false,
  plots: {}
};

describe("JobForm", () => {
  it("shows KW helper text when KW permutation selected", async () => {
    render(
      <JobForm defaults={defaults} isCreating={false} onCreate={vi.fn()} createStatus="idle" />
    );
    await userEvent.click(screen.getByLabelText(/job type/i));
    await userEvent.click(screen.getByRole("option", { name: /kw permutation/i }));
    expect(screen.getByTestId("kw-helper")).toHaveTextContent(/at least three csv files/i);
  });

  it("requires primary file before submit", async () => {
    const onCreate = vi.fn();
    render(<JobForm defaults={defaults} isCreating={false} onCreate={onCreate} createStatus="idle" />);
    await userEvent.click(screen.getByRole("button", { name: /start job/i }));
    expect(onCreate).not.toHaveBeenCalled();
    expect(await screen.findByText(/please select at least one csv/i)).toBeVisible();
  });

  it("submits payload with descriptive job type and files array", async () => {
    const onCreate = vi.fn();
    render(<JobForm defaults={defaults} isCreating={false} onCreate={onCreate} createStatus="idle" />);
    await userEvent.click(screen.getByLabelText(/job type/i));
    await userEvent.click(screen.getByRole("option", { name: /descriptive only/i }));

    const file = new File(["a,b,c"], "data.csv", { type: "text/csv" });
    const input = screen.getByTestId("files-input") as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    await userEvent.click(screen.getByRole("button", { name: /start job/i }));
    expect(onCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        jobType: JobType.DESCRIPTIVE_ONLY,
        files: [expect.any(File)]
      })
    );
  });

  it("shows filename after selection and updates status on success", async () => {
    const onCreate = vi.fn();
    const { rerender } = render(
      <JobForm defaults={defaults} isCreating={false} onCreate={onCreate} createStatus="idle" />
    );
    const input = screen.getByTestId("files-input") as HTMLInputElement;
    const file = new File(["contents"], "selected.csv", { type: "text/csv" });
    await userEvent.upload(input, file);
    expect(screen.getByText(/selected.csv/i)).toBeVisible();

    await userEvent.click(screen.getByRole("button", { name: /start job/i }));
    expect(screen.getByText(/selected.csv — Uploading/i)).toBeVisible();
    rerender(
      <JobForm
        defaults={defaults}
        isCreating={false}
        onCreate={onCreate}
        createStatus="success"
      />
    );
    expect(screen.getByText(/selected.csv — Uploaded/i)).toBeVisible();
  });

  it("shows failed status when upload fails", async () => {
    const onCreate = vi.fn();
    const { rerender } = render(
      <JobForm defaults={defaults} isCreating={false} onCreate={onCreate} createStatus="idle" />
    );
    const input = screen.getByTestId("files-input") as HTMLInputElement;
    const file = new File(["contents"], "third.csv", { type: "text/csv" });
    await userEvent.upload(input, file);
    expect(screen.getByText(/third.csv/i)).toBeVisible();

    await userEvent.click(screen.getByRole("button", { name: /start job/i }));
    rerender(
      <JobForm
        defaults={defaults}
        isCreating={false}
        onCreate={onCreate}
        createStatus="error"
        error="Upload failed"
      />
    );
    expect(screen.getByText(/third.csv — Failed: Upload failed/i)).toBeVisible();
  });

  it("requires at least three files for KW permutation", async () => {
    const onCreate = vi.fn();
    render(<JobForm defaults={defaults} isCreating={false} onCreate={onCreate} createStatus="idle" />);
    await userEvent.click(screen.getByLabelText(/job type/i));
    await userEvent.click(screen.getByRole("option", { name: /kw permutation/i }));

    const input = screen.getByTestId("files-input") as HTMLInputElement;
    const files = [
      new File(["one"], "a.csv", { type: "text/csv" }),
      new File(["two"], "b.csv", { type: "text/csv" })
    ];
    fireEvent.change(input, { target: { files } });

    await userEvent.click(screen.getByRole("button", { name: /start job/i }));
    expect(onCreate).not.toHaveBeenCalled();
    expect(await screen.findByText(/requires at least three csv files/i)).toBeVisible();
  });
});
