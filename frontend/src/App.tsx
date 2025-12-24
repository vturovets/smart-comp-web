import { ApiStatusCard } from "./components/ApiStatusCard";
import { env } from "./config/env";

function App() {
  return (
    <main className="page">
      <header>
        <p className="eyebrow">Smart Comp</p>
        <h1>Web Platform Scaffold</h1>
        <p className="lede">
          FastAPI + Celery backend with a React/Vite front-end. Configure your API base URL via
          <code>VITE_API_BASE_URL</code> to connect the pieces.
        </p>
      </header>

      <section className="panel">
        <ApiStatusCard apiBaseUrl={env.apiBaseUrl} />
      </section>
    </main>
  );
}

export default App;
