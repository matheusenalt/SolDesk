import { useEffect, useRef, useState } from "react";
import { ApiError, request } from "./workspace-api";
import { uploadFile } from "./media-api";
import { mediaStrings as s } from "./media-strings";
import type { Entry } from "./WorkArea";

type Asset = {
  id: string;
  filename: string;
  size: number;
  kind: string;
  validated: boolean;
  purgado_em: string | null;
};
type Job = {
  id: string;
  status: string;
  attachment_id: string;
  attempts: number;
  raw_text: string | null;
  organized_text: string | null;
  error: string | null;
  segments: { text: string; uncertain: boolean }[];
  warnings: unknown[];
  provider_metadata: { simulado?: boolean };
  template_snapshot: { version: number };
};
const friendly = (error: unknown) =>
  error instanceof ApiError ? error.message : s.error;

export function FilePanel({
  ownerType,
  ownerId,
  audio = false,
}: {
  ownerType: string;
  ownerId: string;
  audio?: boolean;
}) {
  const [items, setItems] = useState<Asset[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [links, setLinks] = useState<
    Record<string, { url: string; expires_in: number }>
  >({});
  async function load() {
    setItems(await request<Asset[]>(`/files/${ownerType}/${ownerId}`));
  }
  useEffect(() => {
    setLinks({});
    void load().catch((err) => setError(friendly(err)));
  }, [ownerType, ownerId]);
  return (
    <section className="file-panel" aria-label={s.attachments}>
      <h4>{s.attachments}</h4>
      {error && <p role="alert">! {error}</p>}
      {message && <p role="status">{message}</p>}
      {!audio && (
        <form
          className="workspace-form"
          onSubmit={(event) => {
            event.preventDefault();
            const input = event.currentTarget.elements.namedItem(
              "attachment",
            ) as HTMLInputElement;
            const file = input.files?.[0];
            if (!file) return;
            setBusy(true);
            setError("");
            setMessage(s.sending);
            void uploadFile(`/files/${ownerType}/${ownerId}`, file)
              .then(async () => {
                await load();
                setMessage(s.saved);
                input.value = "";
              })
              .catch((err) => {
                setMessage("");
                setError(friendly(err));
              })
              .finally(() => setBusy(false));
          }}
        >
          <label>
            {s.attachment}
            <input
              aria-label={s.attachment}
              name="attachment"
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.txt"
              required
            />
          </label>
          <button disabled={busy}>{s.upload}</button>
        </form>
      )}
      {!items.length && <p>{s.empty}</p>}
      {items.map((item) => (
        <article key={item.id}>
          <p>
            {item.filename} · {item.size} {s.bytes}
          </p>
          {item.purgado_em ? (
            <p>{s.removed}</p>
          ) : (
            item.validated && (
              <button
                type="button"
                disabled={busy}
                onClick={() => {
                  setBusy(true);
                  setError("");
                  void request<{ url: string; expires_in: number }>(
                    `/attachments/${item.id}/link`,
                    "POST",
                  )
                    .then((value) =>
                      setLinks((current) => ({ ...current, [item.id]: value })),
                    )
                    .catch((err) => setError(friendly(err)))
                    .finally(() => setBusy(false));
                }}
              >
                {s.link}
              </button>
            )
          )}
          {links[item.id] && !item.purgado_em && (
            <>
              <p>
                {s.expires} {links[item.id].expires_in} {s.seconds}
              </p>
              {item.kind === "audio" ? (
                <audio controls src={links[item.id].url} />
              ) : (
                <a href={links[item.id].url} download>
                  {s.download} · {item.filename}
                </a>
              )}
            </>
          )}
        </article>
      ))}
    </section>
  );
}

export function AudioReview({
  record,
  isAuthor,
  onRecord,
  onAcknowledged,
}: {
  record: Entry;
  isAuthor: boolean;
  onRecord: (value: Entry) => void;
  onAcknowledged: (value: boolean) => void;
}) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [checked, setChecked] = useState(false);
  const revision = useRef(record.revision);
  revision.current = record.revision;
  const jobKey = useRef("");
  const active = useRef(true);
  async function load() {
    const result = await request<{ record: Entry; jobs: Job[] }>(
      `/records/${record.id}/processing`,
    );
    if (!active.current) return;
    setJobs(result.jobs);
    const key = result.jobs[0]
      ? result.jobs[0].id + ":" + result.jobs[0].status
      : "";
    if (key !== jobKey.current) {
      jobKey.current = key;
      setChecked(false);
      onAcknowledged(false);
    }
    if (result.record.revision !== revision.current) {
      revision.current = result.record.revision;
      onRecord(result.record);
    }
  }
  useEffect(() => {
    active.current = true;
    let alive = true;
    const refresh = () => {
      if (alive)
        void load().catch((err) => {
          if (alive) setError(friendly(err));
        });
    };
    refresh();
    const timer = setInterval(refresh, 3000);
    return () => {
      alive = false;
      active.current = false;
      clearInterval(timer);
    };
  }, [record.id]);
  const latest = jobs[0];
  if (!latest) return error ? <p role="alert">! {error}</p> : null;
  const editable =
    isAuthor &&
    !["confirmado", "publicado", "cancelado"].includes(record.status);
  return (
    <section className="audio-review" aria-label={s.processing}>
      <h4>{s.processing}</h4>
      <p>
        {s.states[latest.status as keyof typeof s.states] || latest.status} ·{" "}
        {s.attempts}: {latest.attempts}
      </p>
      {error && <p role="alert">! {error}</p>}
      {latest.error && <p role="alert">! {latest.error}</p>}
      {latest.status === "aguardando" && <p>{s.waiting}</p>}
      {latest.provider_metadata.simulado && <p>{s.mock}</p>}
      {latest.raw_text && (
        <>
          <h5>{s.raw}</h5>
          <p>{latest.raw_text}</p>
        </>
      )}
      {latest.segments
        .filter((segment) => segment.uncertain)
        .map((segment, index) => (
          <p key={index}>
            <mark>
              {s.uncertain}: {segment.text}
            </mark>
          </p>
        ))}
      {!!latest.warnings.length && <p role="note">{s.sensitive}</p>}
      {latest.organized_text && (
        <>
          <h5>
            {s.organized} · {s.templateVersion}:{" "}
            {latest.template_snapshot.version}
          </h5>
          <p>{latest.organized_text}</p>
        </>
      )}
      {record.ditado_texto && (
        <>
          <h5>{s.liveText}</h5>
          <p>{record.ditado_texto}</p>
        </>
      )}
      {editable && latest.status === "concluido" && (
        <label>
          <input
            type="checkbox"
            checked={checked}
            onChange={(event) => {
              setChecked(event.target.checked);
              onAcknowledged(event.target.checked);
            }}
          />
          {s.ack}
        </label>
      )}
      <button
        type="button"
        disabled={busy}
        onClick={() => void load().catch((err) => setError(friendly(err)))}
      >
        {s.refresh}
      </button>
      {editable && ["erro", "concluido"].includes(latest.status) && (
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            setBusy(true);
            setError("");
            void request(`/audio-jobs/${latest.id}/retry`, "POST", {
              revision: record.revision,
            })
              .then(load)
              .catch((err) => setError(friendly(err)))
              .finally(() => setBusy(false));
          }}
        >
          {s.retry}
        </button>
      )}
      {editable && latest.status !== "descartado" && (
        <>
          <p>{s.discardHint}</p>
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              setBusy(true);
              setError("");
              void request<Entry>(`/audio-jobs/${latest.id}/discard`, "POST", {
                revision: record.revision,
              })
                .then(async (value) => {
                  onRecord(value);
                  await load();
                })
                .catch((err) => setError(friendly(err)))
                .finally(() => setBusy(false));
            }}
          >
            {s.discard}
          </button>
        </>
      )}
      <FilePanel
        key={latest.id + ":" + latest.status}
        ownerType="record"
        ownerId={record.id}
        audio
      />
      {jobs.length > 1 && (
        <details>
          <summary>{s.previous}</summary>
          {jobs.slice(1).map((job) => (
            <article key={job.id}>
              <p>
                {s.states[job.status as keyof typeof s.states] || job.status}
              </p>
              <p>{job.raw_text}</p>
            </article>
          ))}
        </details>
      )}
    </section>
  );
}

export function MediaConfiguration({
  administrator,
}: {
  administrator: boolean;
}) {
  const [templates, setTemplates] = useState<
    {
      type: string;
      version: number;
      fields: { key: string; label: string; markers: string[] }[];
    }[]
  >([]);
  const [terms, setTerms] = useState<{ term: string; aliases: string[] }[]>([]);
  const [preferences, setPreferences] = useState<{
    retention: string;
    retention_days: number;
    live_dictation_enabled: boolean;
  } | null>(null);
  const [health, setHealth] = useState<Record<string, boolean | string>>({});
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  async function load() {
    const values = await Promise.all([
      request<typeof templates>("/media/templates"),
      request<typeof terms>("/media/glossary"),
      request<NonNullable<typeof preferences>>("/media/settings"),
      request<typeof health>("/media/health"),
    ]);
    setTemplates(values[0]);
    setTerms(values[1]);
    setPreferences(values[2]);
    setHealth(values[3]);
  }
  useEffect(() => {
    void load().catch((err) => setError(friendly(err)));
  }, []);
  async function perform(action: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await action();
      await load();
      setMessage(s.savedConfig);
    } catch (err) {
      setError(friendly(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section aria-label={s.config}>
      <h4>{s.config}</h4>
      {error && <p role="alert">! {error}</p>}
      {message && <p role="status">{message}</p>}
      <h5>{s.health}</h5>
      {["redis", "worker", "dispatcher"].map((key) => (
        <p key={key}>
          {s.healthLabels[key as keyof typeof s.healthLabels]}:{" "}
          {health[key] === true ? s.available : s.unavailable}
        </p>
      ))}
      <h5>{s.glossary}</h5>
      <p>{s.glossaryHint}</p>
      {terms.map((term) => (
        <p key={term.term}>
          {term.term} · {term.aliases.join(", ")}
        </p>
      ))}
      {administrator && (
        <form
          className="workspace-form"
          onSubmit={(event) => {
            event.preventDefault();
            const data = new FormData(event.currentTarget);
            void perform(() =>
              request("/media/glossary", "POST", {
                term: data.get("term"),
                aliases: String(data.get("aliases") || "")
                  .split("\n")
                  .map((value) => value.trim())
                  .filter(Boolean),
              }),
            );
          }}
        >
          <label>
            {s.term}
            <input name="term" required maxLength={80} />
          </label>
          <label>
            {s.aliases}
            <textarea name="aliases" />
          </label>
          <button disabled={busy}>{s.save}</button>
        </form>
      )}
      <h5>{s.templates}</h5>
      <p>{s.fieldsHint}</p>
      {templates.map((template) => (
        <form
          key={template.type + ":" + template.version}
          className="workspace-form"
          onSubmit={(event) => {
            event.preventDefault();
            const data = new FormData(event.currentTarget);
            const fields = template.fields.flatMap((field, index) =>
              data.has(`remove_${index}`)
                ? []
                : [
                    {
                      key: field.key,
                      label: String(data.get(`label_${index}`)),
                      markers: String(data.get(`markers_${index}`))
                        .split(",")
                        .map((marker) => marker.trim())
                        .filter(Boolean),
                    },
                  ],
            );
            const added = String(data.get("new_label") || "").trim();
            if (added) {
              const key = Array.from(
                { length: 10 },
                (_, index) => "custom_" + String.fromCharCode(97 + index),
              ).find((key) => !fields.some((field) => field.key === key))!;
              fields.push({
                key,
                label: added,
                markers: String(data.get("new_markers") || added)
                  .split(",")
                  .map((marker) => marker.trim())
                  .filter(Boolean),
              });
            }
            void perform(() =>
              request("/media/templates", "POST", {
                type: template.type,
                expected_version: template.version,
                fields,
              }),
            );
          }}
        >
          <p>
            {s.kinds[template.type as keyof typeof s.kinds]} · {s.version}:{" "}
            {template.version}
          </p>
          {template.fields.map((field, index) => (
            <fieldset key={field.key}>
              <legend>{field.label}</legend>
              <label>
                {s.fieldLabel}
                <input
                  aria-label={`${s.fieldLabel} ${field.label}`}
                  name={`label_${index}`}
                  defaultValue={field.label}
                  readOnly={!administrator}
                  required
                  maxLength={80}
                />
              </label>
              <label>
                {s.fieldMarkers}
                <input
                  aria-label={`${s.fieldMarkers} ${field.label}`}
                  name={`markers_${index}`}
                  defaultValue={field.markers.join(", ")}
                  readOnly={!administrator}
                  required
                  maxLength={480}
                />
              </label>
              {administrator && (
                <label>
                  <input name={`remove_${index}`} type="checkbox" />
                  {s.removeField}
                </label>
              )}
            </fieldset>
          ))}
          {administrator && template.fields.length < 10 && (
            <fieldset>
              <legend>{s.newField}</legend>
              <label>
                {s.fieldLabel}
                <input name="new_label" maxLength={80} />
              </label>
              <label>
                {s.fieldMarkers}
                <input name="new_markers" maxLength={480} />
              </label>
            </fieldset>
          )}
          {administrator && <button disabled={busy}>{s.save}</button>}
        </form>
      ))}
      {preferences && administrator && (
        <form
          key={JSON.stringify(preferences)}
          className="workspace-form"
          onSubmit={(event) => {
            event.preventDefault();
            const data = new FormData(event.currentTarget);
            void perform(() =>
              request("/media/settings", "PATCH", {
                retention: data.get("retention"),
                retention_days: Number(data.get("days")),
                live_dictation_enabled: data.has("live"),
              }),
            );
          }}
        >
          <p>{s.retentionHint}</p>
          <label>
            {s.retention}
            <select
              name="retention"
              aria-label={s.retention}
              defaultValue={preferences.retention}
            >
              {Object.entries(s.retentions).map(([key, text]) => (
                <option key={key} value={key}>
                  {text}
                </option>
              ))}
            </select>
          </label>
          <label>
            {s.days}
            <input
              name="days"
              type="number"
              min={1}
              max={3650}
              defaultValue={preferences.retention_days}
              required
            />
          </label>
          <label>
            <input
              name="live"
              type="checkbox"
              defaultChecked={preferences.live_dictation_enabled}
            />
            {s.liveEnabled}
          </label>
          <button disabled={busy}>{s.save}</button>
        </form>
      )}
    </section>
  );
}
