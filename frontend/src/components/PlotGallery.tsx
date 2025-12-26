import { useQueries } from "@tanstack/react-query";
import Plot from "react-plotly.js";

import { PlotRef } from "../api";

interface PlotGalleryProps {
  jobId: string;
  plots?: PlotRef[];
  loadPlot: (artifactName: string) => Promise<{ data: any; layout?: any }>;
}

export function PlotGallery({ jobId, plots = [], loadPlot }: PlotGalleryProps) {
  const queries = useQueries({
    queries: plots.map((plot) => ({
      queryKey: ["plot", jobId, plot.artifactName],
      queryFn: () => loadPlot(plot.artifactName)
    }))
  });

  if (!plots.length) return null;

  return (
    <div className="plot-grid">
      {queries.map((query, index) => {
        const ref = plots[index];
        if (query.isPending) return <p key={ref.artifactName}>Loading plot {ref.artifactName}…</p>;
        if (query.isError) {
          return (
            <p key={ref.artifactName} className="muted">
              Failed to render {ref.artifactName}
            </p>
          );
        }
        const payload = query.data;
        return (
          <Plot
            key={ref.artifactName}
            data={payload?.data ?? []}
            layout={{ title: ref.kind || ref.artifactName, ...(payload?.layout ?? {}) }}
            useResizeHandler
            style={{ width: "100%", height: "100%" }}
            className="plot-card"
            config={{ displaylogo: false, responsive: true }}
          />
        );
      })}
    </div>
  );
}
