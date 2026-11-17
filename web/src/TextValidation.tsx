import { useEffect, useRef, useState } from "react";
import { request, ApiError } from "./workspace-api";
import { evolutionStrings as s } from "./evolution-strings";

type Validation = {
  status: string;
  version: {
    id: string;
    content_hash: string;
    record_revision: number;
    content: {
      record: { texto_original: string; texto_organizado: string | null };
      transcription: { organized_text: string } | null;
    };
  } | null;
  validations: {
    id: string;
    validated_by: string;
    validado_em: string;
    version_id: string;
  }[];
};

export function TextValidation({
  id,
  revision,
  timezone,
}: {
  id: string;
  revision: number;
  timezone: string;
}) {
  const [value, setValue] = useState<Validation | null>(null);
  const [checked, setChecked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const currentVersion = useRef("");
  useEffect(() => {
    let active = true;
    const load = () =>
      void request<Validation>(`/records/${id}/text-validation`)
        .then((data) => {
          if (!active) return;
          if (currentVersion.current !== data.version?.id) setChecked(false);
          currentVersion.current = data.version?.id || "";
          setValue(data);
          setError("");
        })
        .catch((err) => {
          if (active) setError(err instanceof ApiError ? err.message : s.error);
        });
    load();
    const timer = setInterval(load, 4000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [id, revision]);
  async function validate() {
    if (!value?.version || !checked) return;
    setBusy(true);
    setError("");
    try {
      const result = await request<Validation>(
        `/records/${id}/text-validations`,
        "POST",
        {
          version_id: value.version.id,
          content_hash: value.version.content_hash,
          reviewed: true,
        },
      );
      setValue(result);
      window.dispatchEvent(new Event("soldesk-text-validation"));
      setChecked(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : s.error);
      setChecked(false);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section aria-label={s.validation} className="work-card">
      <h5>
        {s.validation}:{" "}
        {s.states[error ? "falha" : value?.status || "processando"]}
      </h5>
      {error && <p role="alert">{error}</p>}
      {error && (
        <button
          type="button"
          onClick={() =>
            void request<Validation>(`/records/${id}/text-validation`)
              .then((v) => {
                setValue(v);
                setError("");
              })
              .catch((e) =>
                setError(e instanceof ApiError ? e.message : s.error),
              )
          }
        >
          {s.retry}
        </button>
      )}
      {value?.version && (
        <>
          <p>
            {s.version}: {value.version.record_revision}
          </p>
          <p>{s.text}</p>
          <p>
            {value.version.content.transcription?.organized_text ||
              value.version.content.record.texto_organizado ||
              value.version.content.record.texto_original}
          </p>
          {value.status === "nao_validado" && (
            <>
              <label>
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={(e) => setChecked(e.target.checked)}
                />
                {s.reviewed}
              </label>
              <button
                type="button"
                disabled={!checked || busy || !!error}
                onClick={() => void validate()}
              >
                {s.now}
              </button>
              <button
                type="button"
                onClick={() => {
                  setChecked(false);
                  setMessage(s.deferred);
                }}
              >
                {s.later}
              </button>
            </>
          )}
          <details>
            <summary>{s.validations}</summary>
            {value.validations.map((event) => (
              <p key={event.id}>
                {s.validatedBy}: {event.validated_by} ·{" "}
                {new Intl.DateTimeFormat("pt-BR", {
                  timeZone: timezone,
                  dateStyle: "short",
                  timeStyle: "short",
                }).format(new Date(event.validado_em))}{" "}
                · {event.version_id}
              </p>
            ))}
          </details>
        </>
      )}
      {message && <p role="status">{message}</p>}
    </section>
  );
}

export function ValidationBadge({
  id,
  revision,
}: {
  id: string;
  revision: number;
}) {
  const [status, setStatus] = useState("processando");
  useEffect(() => {
    let active = true;
    const load = () =>
      void request<Validation>(`/records/${id}/text-validation`)
        .then((v) => {
          if (active) setStatus(v.status);
        })
        .catch(() => {
          if (active) setStatus("falha");
        });
    load();
    window.addEventListener("soldesk-text-validation", load);
    return () => {
      active = false;
      window.removeEventListener("soldesk-text-validation", load);
    };
  }, [id, revision]);
  return (
    <p>
      {s.validation}: {s.states[status]}
    </p>
  );
}

export function ValidationQueue({ onOpen }: { onOpen: (id: string) => void }) {
  const [offset, setOffset] = useState(0);
  const [rows, setRows] = useState<{ record_id: string; status: string }[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let active = true;
    void request<{ items: typeof rows; total: number }>(
      `/records/text-validations/pending?offset=${offset}&limit=20`,
    )
      .then((data) => {
        if (active) {
          setRows(data.items);
          setTotal(data.total);
          setError("");
        }
      })
      .catch((e) => {
        if (active) setError(e instanceof ApiError ? e.message : s.error);
      });
    return () => {
      active = false;
    };
  }, [offset, refresh]);
  return (
    <section aria-label={s.pendingText}>
      <h4>{s.pendingText}</h4>
      {error && <p role="alert">{error}</p>}
      <button onClick={() => setRefresh((v) => v + 1)}>{s.refresh}</button>
      {rows.map((row) => (
        <article className="work-card" key={row.record_id}>
          <p>
            {row.record_id} · {s.states[row.status]}
          </p>
          <button onClick={() => onOpen(row.record_id)}>{s.view}</button>
        </article>
      ))}
      <button disabled={!offset} onClick={() => setOffset((v) => v - 20)}>
        {s.previous}
      </button>
      <button
        disabled={offset + 20 >= total}
        onClick={() => setOffset((v) => v + 20)}
      >
        {s.nextPage}
      </button>
    </section>
  );
}
