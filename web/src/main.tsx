import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { loadStatus, type ServerInfo } from "./api";
import { strings as s } from "./strings";
import { Workspace } from "./Workspace";
import "./styles.css";

function App() {
  const [dark, setDark] = useState(
    () => matchMedia("(prefers-color-scheme: dark)").matches,
  );
  const [info, setInfo] = useState<ServerInfo | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }, [dark]);
  useEffect(() => {
    const controller = new AbortController();
    loadStatus(controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) {
          setInfo(result);
          setState("ready");
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setInfo(null);
          setState("error");
        }
      });
    return () => controller.abort();
  }, [attempt]);
  return (
    <div className="shell">
      <aside className="sidebar">
        <a className="brand" href="#inicio">
          <span className="sun" aria-hidden="true">
            ☀
          </span>
          {s.product}
        </a>
        <nav aria-label={s.overview}>
          <a href="#inicio" aria-current="page">
            <span aria-hidden="true">◈</span>
            {s.overview}
          </a>
          <a href="#instalacao">
            <span aria-hidden="true">◇</span>
            {s.instance}
          </a>
        </nav>
        <div className="sidebar-foot">
          <span className="eyebrow">COMMUNITY</span>
          <p>{s.footer}</p>
        </div>
      </aside>
      <main id="inicio">
        <header>
          <span className="breadcrumb">{s.overview}</span>
          <button
            className="theme"
            onClick={() => setDark(!dark)}
            aria-label={s.theme}
            aria-pressed={dark}
          >
            {dark ? "☀" : "◐"}
          </button>
        </header>
        <section className="hero" aria-labelledby="welcome">
          <span className="eyebrow">{s.foundation}</span>
          <h1 id="welcome">{s.tagline}</h1>
          <p className="lead">{s.subtitle}</p>
          <p className="intro">{s.intro}</p>
          <div className="hero-art" aria-hidden="true">
            <div className="orbit one" />
            <div className="orbit two" />
            <div className="orb">☀</div>
            <span className="spark a">✦</span>
            <span className="spark b">✦</span>
          </div>
        </section>
        <section
          className="connection"
          id="instalacao"
          aria-labelledby="connection-title"
        >
          <div className="connection-top">
            <div>
              <h2 id="connection-title">{s.statusTitle}</h2>
              <p>{s.foundationDescription}</p>
            </div>
            <span role="status" className={`status ${state}`}>
              <span aria-hidden="true">
                {state === "ready" ? "✓" : state === "error" ? "!" : "◷"}
              </span>
              {state === "ready"
                ? s.connected
                : state === "error"
                  ? s.disconnected
                  : s.checking}
            </span>
          </div>
          {state === "ready" && info && (
            <dl>
              <div>
                <dt>{s.mode}</dt>
                <dd>{info.mode === "community" ? s.community : s.cloud}</dd>
              </div>
              <div>
                <dt>{s.version}</dt>
                <dd>{info.api_version}</dd>
              </div>
              <div className="instance-id">
                <dt>{s.instanceId}</dt>
                <dd>{info.instance_id}</dd>
              </div>
            </dl>
          )}
          {state === "error" && (
            <div role="alert" className="error">
              <p>{s.error}</p>
              <button
                onClick={() => {
                  setState("loading");
                  setAttempt(attempt + 1);
                }}
              >
                {s.retry}
              </button>
            </div>
          )}
        </section>
        <Workspace />
        <section className="next" aria-labelledby="next-title">
          <div className="section-title">
            <h2 id="next-title">{s.future}</h2>
            <span>{s.planned}</span>
          </div>
          <div className="cards">
            {s.cards.map((card) => (
              <article key={card.icon}>
                <span className="card-number" aria-hidden="true">
                  {card.icon}
                </span>
                <h3>{card.title}</h3>
                <p>{card.text}</p>
              </article>
            ))}
          </div>
          <p className="note">{s.noBusiness}</p>
        </section>
        <footer>
          {s.product}
          <span aria-hidden="true"> · </span>
          {s.footer}
        </footer>
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
