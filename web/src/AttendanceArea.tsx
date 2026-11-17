import { useEffect, useRef, useState, type FormEvent } from "react";
import { request, ApiError } from "./workspace-api";
import { evolutionStrings as s } from "./evolution-strings";
import { AudioCapture } from "./AudioCapture";
import { AudioReview } from "./MediaPanels";
import { TextValidation } from "./TextValidation";
import { uploadFile } from "./media-api";
import { localToUtc } from "./work-time";
import type { Entry } from "./WorkArea";

type Attendance = {
  id: string;
  revision: number;
  assignee_id: string;
  status: string;
  next_action: string;
  retomada_em: string | null;
  result: string;
  record: Entry;
  updates?: Entry[];
  updates_total?: number;
  events?: {
    action: string;
    actor_id: string;
    after: Record<string, unknown>;
    ocorrido_em: string;
  }[];
};
type Option = { id: string; name: string };
const groups = ["em_andamento", "aguardando_retomada", "finalizado", "pending"];

export function AttendanceArea({
  userId,
  role,
  timezone,
}: {
  userId: string;
  role: string;
  timezone: string;
}) {
  const [rows, setRows] = useState<Record<string, Attendance[]>>({});
  const [clients, setClients] = useState<Option[]>([]);
  const [people, setPeople] = useState<Option[]>([]);
  const [selected, setSelected] = useState<Attendance | null>(null);
  const [kind, setKind] = useState("em_andamento");
  const [internal, setInternal] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [live, setLive] = useState("");
  const [text, setText] = useState("");
  const [captureBusy, setCaptureBusy] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState<Entry | null>(null);
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState(0);
  const [totals, setTotals] = useState<Record<string, number>>({});
  const lock = useRef(false);
  const pending = useRef<{
    key: string;
    path: string;
    body: unknown;
    record?: Entry;
  } | null>(null);
  const [recovering, setRecovering] = useState(false);
  const date = (value: string) =>
    new Intl.DateTimeFormat("pt-BR", {
      timeZone: timezone,
      dateStyle: "short",
      timeStyle: "short",
    }).format(new Date(value));
  async function refresh() {
    const values = await Promise.all(
      groups.map((group) =>
        request<{ items: Attendance[]; total: number }>(
          `/attendances?mine=true&limit=10&offset=${page * 10}&${group === "pending" ? "pending=true" : `status=${group}`}`,
        ),
      ),
    );
    setRows(Object.fromEntries(groups.map((g, i) => [g, values[i].items])));
    setTotals(Object.fromEntries(groups.map((g, i) => [g, values[i].total])));
  }
  useEffect(() => {
    let active = true;
    void Promise.all([
      request<{ items: Option[] }>("/clients?limit=100"),
      request<Option[]>("/assignment-options"),
    ])
      .then(([c, p]) => {
        if (active) {
          setClients(c.items);
          setPeople(p);
        }
      })
      .catch((e) => {
        if (active) setError(e instanceof ApiError ? e.message : s.error);
      });
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    void refresh().catch((e) =>
      setError(e instanceof ApiError ? e.message : s.error),
    );
  }, [page]);
  useEffect(() => {
    if (!recovering) return;
    const warn = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [recovering]);
  async function open(id: string, skip = 0) {
    setSelected(
      await request<Attendance>(`/attendances/${id}?offset=${skip}&limit=20`),
    );
    setOffset(skip);
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError("");
    const form = event.currentTarget;
    const data = new FormData(form);
    const value = (key: string) => String(data.get(key) || "");
    try {
      if (!pending.current) {
        const occurred = value("ocorrido_em");
        const resumed = value("retomada_em");
        if (
          (occurred && !localToUtc(occurred, timezone)) ||
          (resumed && !localToUtc(resumed, timezone))
        )
          throw new Error(s.invalidTime);
        const body = selected
          ? {
              revision: selected.revision,
              texto_original: text,
              action: value("action"),
              next_action: value("next_action"),
              result: value("result"),
              ...(value("assignee_id")
                ? { assignee_id: value("assignee_id") }
                : {}),
              retomada_em: resumed ? localToUtc(resumed, timezone) : null,
              ...(occurred
                ? { ocorrido_em: localToUtc(occurred, timezone) }
                : {}),
            }
          : {
              type: "finalizacao",
              internal_activity: internal,
              client_id: value("client_id") || null,
              texto_original: text,
              category: value("category"),
              system: value("system"),
              ...(kind === "em_andamento"
                ? { assignee_id: value("assignee_id") || userId }
                : {}),
              ...(occurred
                ? { ocorrido_em: localToUtc(occurred, timezone) }
                : {}),
            };
        if (
          (!text.trim() && !file) ||
          (!selected && kind === "finalizacao" && !text.trim())
        )
          throw new Error(s.descriptionRequired);
        pending.current = {
          key: crypto.randomUUID(),
          body,
          path: selected
            ? `/attendances/${selected.id}/updates`
            : kind === "em_andamento"
              ? "/attendances"
              : "/records",
        };
      }
      const p = pending.current;
      if (!p.record) {
        const response = await request<
          Attendance | Entry | { attendance: Attendance; update: Entry }
        >(p.path, "POST", p.body, { "Idempotency-Key": p.key });
        p.record =
          "attendance" in response
            ? response.update
            : "record" in response
              ? response.record
              : response;
      }
      setSaved(p.record);
      if (file) {
        const current = await request<Entry>(`/records/${p.record.id}`);
        await uploadFile(
          `/records/${current.id}/audio?revision=${current.revision}`,
          file,
        );
      }
      const path = p.path;
      pending.current = null;
      setRecovering(false);
      setFile(null);
      setText("");
      setLive("");
      form.reset();
      if (selected) await open(selected.id);
      else if (path === "/attendances") await open(p.record.id);
      await refresh();
    } catch (e) {
      if (e instanceof ApiError && e.status < 500 && !pending.current?.record) {
        pending.current = null;
        setRecovering(false);
        if (e.status === 409 && selected) await open(selected.id);
      } else if (pending.current) {
        setRecovering(true);
      }
      setError(e instanceof Error ? e.message : s.error);
    } finally {
      setBusy(false);
      lock.current = false;
    }
  }
  const [action, setAction] = useState("atualizar");
  const options = people.map((p) => (
    <option key={p.id} value={p.id}>
      {p.name}
    </option>
  ));
  const canWrite =
    selected &&
    selected.status !== "finalizado" &&
    (role !== "tecnico" || selected.assignee_id === userId);
  return (
    <section aria-label={s.dashboard}>
      <h4>{s.dashboard}</h4>
      {error && <p role="alert">{error}</p>}
      <button
        disabled={busy || recovering}
        onClick={() => {
          setSelected(null);
          setSaved(null);
          setText("");
          setFile(null);
          setAction("atualizar");
        }}
      >
        {s.openAttendance}
      </button>
      <button
        disabled={busy}
        onClick={() =>
          void refresh().catch((e) =>
            setError(e instanceof Error ? e.message : s.error),
          )
        }
      >
        {s.refresh}
      </button>
      <div className="workspace-list">
        {groups.map((group) => (
          <section key={group} aria-label={s.groups[group]}>
            <h5>
              {s.groups[group]} ({totals[group] || 0})
            </h5>
            {rows[group]?.map((item) => (
              <article className="work-card" key={item.id}>
                <p>{item.record.client_name || s.internal}</p>
                <p>{item.record.texto_original}</p>
                <p>{item.next_action}</p>
                {item.retomada_em && (
                  <p>
                    {s.resume}: {date(item.retomada_em)}
                  </p>
                )}
                <button
                  disabled={recovering || busy}
                  onClick={() =>
                    void open(item.id).catch((e) =>
                      setError(e instanceof Error ? e.message : s.error),
                    )
                  }
                >
                  {s.open}
                </button>
              </article>
            ))}
          </section>
        ))}
      </div>
      <button disabled={!page} onClick={() => setPage((v) => v - 1)}>
        {s.previous}
      </button>
      <button
        disabled={!groups.some((g) => (totals[g] || 0) > (page + 1) * 10)}
        onClick={() => setPage((v) => v + 1)}
      >
        {s.nextPage}
      </button>
      {(!selected || canWrite) && (
        <form className="workspace-form" onSubmit={(e) => void submit(e)}>
          <h5>{selected ? s.addUpdate : s.openAttendance}</h5>
          {recovering && <p role="status">{s.retrySaved}</p>}
          <fieldset disabled={busy || recovering}>
            {!selected ? (
              <>
                <label>
                  {s.mode}
                  <select
                    aria-label={s.mode}
                    value={kind}
                    onChange={(e) => setKind(e.target.value)}
                  >
                    <option value="finalizacao">{s.finalization}</option>
                    <option value="em_andamento">{s.ongoing}</option>
                  </select>
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={internal}
                    onChange={(e) => setInternal(e.target.checked)}
                  />
                  {s.internal}
                </label>
                <label>
                  {s.client}
                  <select
                    aria-label={s.client}
                    name="client_id"
                    required={!internal}
                  >
                    <option value="">{s.select}</option>
                    {clients.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  {s.category}
                  <input name="category" maxLength={80} />
                </label>
                <label>
                  {s.system}
                  <input name="system" maxLength={80} />
                </label>
                {kind === "em_andamento" && (
                  <label>
                    {s.responsible}
                    <select
                      aria-label={s.responsible}
                      name="assignee_id"
                      defaultValue={userId}
                    >
                      {options}
                    </select>
                  </label>
                )}
              </>
            ) : (
              <>
                <label>
                  {s.action}
                  <select
                    aria-label={s.action}
                    name="action"
                    value={action}
                    onChange={(e) => setAction(e.target.value)}
                  >
                    <option value="atualizar">{s.addUpdate}</option>
                    <option value="transferir">{s.transfer}</option>
                    <option value="finalizar">{s.finish}</option>
                  </select>
                </label>
                {action === "transferir" && (
                  <label>
                    {s.responsible}
                    <select
                      aria-label={s.responsible}
                      name="assignee_id"
                      required
                    >
                      {options}
                    </select>
                  </label>
                )}
                {action === "finalizar" ? (
                  <label>
                    {s.result}
                    <textarea name="result" required maxLength={20000} />
                  </label>
                ) : (
                  <>
                    <label>
                      {s.nextAction}
                      <textarea
                        name="next_action"
                        maxLength={20000}
                        defaultValue={selected.next_action}
                      />
                    </label>
                    <label>
                      {s.resume} · {timezone}
                      <input type="datetime-local" name="retomada_em" />
                    </label>
                  </>
                )}
              </>
            )}
            <label>
              {s.description}
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                maxLength={20000}
              />
            </label>
            <label>
              {s.occurred} · {timezone}
              <input type="datetime-local" name="ocorrido_em" />
            </label>
            <AudioCapture
              file={file}
              onFile={setFile}
              live={live}
              onLive={setLive}
              onUseLive={() => setText(live)}
              onBusy={setCaptureBusy}
            />
          </fieldset>
          <button disabled={busy || captureBusy}>
            {recovering ? s.retry : s.save}
          </button>
        </form>
      )}
      {saved && (
        <article className="work-card">
          <p>
            {s.saved}: {saved.id}
          </p>
          <TextValidation
            key={saved.id}
            id={saved.id}
            revision={saved.revision}
            timezone={timezone}
          />
          {!selected && (
            <AudioReview
              record={saved}
              isAuthor={saved.author_id === userId}
              onAcknowledged={() => {}}
              onRecord={setSaved}
            />
          )}
        </article>
      )}
      {selected && (
        <article className="workspace-detail">
          <h5>
            {selected.record.client_name || s.internal} ·{" "}
            {s.cycleStates[selected.status as keyof typeof s.cycleStates]}
          </h5>
          <p>{selected.result}</p>
          {[selected.record, ...(selected.updates || [])].map((entry) => (
            <article className="work-card" key={entry.id}>
              <p>
                {date(entry.ocorrido_em)} · {entry.author_name}
              </p>
              <p>{entry.texto_organizado || entry.texto_original}</p>
              <AudioReview
                record={entry}
                isAuthor={entry.author_id === userId}
                onAcknowledged={() => {}}
                onRecord={() =>
                  void open(selected.id, offset).catch((e) =>
                    setError(e instanceof Error ? e.message : s.error),
                  )
                }
              />
              <TextValidation
                id={entry.id}
                revision={entry.revision}
                timezone={timezone}
              />
            </article>
          ))}
          <button
            disabled={!offset}
            onClick={() =>
              void open(selected.id, offset - 20).catch((e) =>
                setError(e instanceof Error ? e.message : s.error),
              )
            }
          >
            {s.previous}
          </button>
          <button
            disabled={offset + 20 >= (selected.updates_total || 0)}
            onClick={() =>
              void open(selected.id, offset + 20).catch((e) =>
                setError(e instanceof Error ? e.message : s.error),
              )
            }
          >
            {s.nextPage}
          </button>
          <details>
            <summary>{s.events}</summary>
            {selected.events?.map((event, i) => (
              <p key={i}>
                {date(event.ocorrido_em)} · {event.actor_id} · {event.action} ·{" "}
                {String(event.after.assignee_id || "")}
              </p>
            ))}
          </details>
        </article>
      )}
    </section>
  );
}
