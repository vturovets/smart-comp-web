import { useEffect, useState } from "react";

export type ApiStatus = "unknown" | "online" | "offline";

interface ApiStatusCardProps {
  apiBaseUrl: string;
}

export function ApiStatusCard({ apiBaseUrl }: ApiStatusCardProps) {
  const [status, setStatus] = useState<ApiStatus>("unknown");

  useEffect(() => {
    const abort = new AbortController();

    fetch(`${apiBaseUrl}/api/health`, { signal: abort.signal })
      .then((response) => setStatus(response.ok ? "online" : "offline"))
      .catch(() => setStatus("offline"));

    return () => abort.abort();
  }, [apiBaseUrl]);

  return (
    <article className="card">
      <header className="card__header">
        <div>
          <p className="eyebrow">API</p>
          <h2>Connectivity</h2>
        </div>
        <span className={`pill pill--${status}`}>{status}</span>
      </header>
      <p className="muted">Base URL: {apiBaseUrl}</p>
      <p className="muted">Probing /api/health on load</p>
    </article>
  );
}
