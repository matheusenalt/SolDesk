import { useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError, request } from "./workspace-api";
import { workStrings as s } from "./work-strings";
import { localInput, localToUtc } from "./work-time";
import { AudioCapture } from "./AudioCapture";
import { AudioReview, FilePanel, MediaConfiguration } from "./MediaPanels";
import { uploadFile } from "./media-api";
import { mediaStrings as ms } from "./media-strings";
import { RelatedArticles } from "./KnowledgeArea";
import { insightStrings as ins } from "./insight-strings";

export type Entry = {
  id: string;
  client_id: string;
  client_name: string;
  author_id: string;
  author_name: string;
  type: string;
  texto_original: string;
  texto_organizado: string | null;
  status: string;
  revision: number;
  ocorrido_em: string;
  enviado_em: string;
  revisado_em: string | null;
  provisional: boolean;
  age_seconds: number;
  article_id: string | null;
  ticket_id: string | null;
  cancellation_reason: string | null;
  origem_record_id: string | null;
  template_version_id: string | null;
  template_version: number | null;
  ditado_texto: string | null;
  category: string;
  system: string;
  article_status: string | null;
};
type Ticket = {
  id: string;
  code: string;
  client_name: string;
  description: string;
  opened_by: string;
  assignee_id: string;
  priority: string;
  category: string;
  system: string;
  status: string;
  revision: number;
  reopen_count: number;
  aberto_em: string;
  opened_by_name: string;
  assignee_id_name: string;
  resolved_by_name: string | null;
  closed_by_name: string | null;
  comments?: {
    id: string;
    author_name: string;
    text: string;
    criado_em: string;
    kind: string;
    mentioned_user_ids: string[];
  }[];
  events?: {
    id: string;
    change: string;
    ocorrido_em: string;
    before: Record<string, unknown>;
    after: Record<string, unknown>;
  }[];
  intervals?: {
    id: string;
    status: string;
    entrada_em: string;
    saida_em: string | null;
  }[];
};
type Notice = {
  id: string;
  type: string;
  reference_type: string;
  reference_id: string;
  criado_em: string;
  lida_em: string | null;
};
type PageResult<T> = { items: T[]; total: number };
type Props = {
  userId: string;
  role: string;
  timezone: string;
  initialClient?: string;
  hidden?: boolean;
  creationRequest?: number;
  focus?: { id: string; ticket: boolean };
  onArticle: (id: string) => void;
};

const transitions: Record<string, string[]> = {
  aberto: [
    "em_andamento",
    "aguardando_esclarecimento",
    "aguardando_terceiros",
    "resolvido",
  ],
  em_andamento: [
    "aguardando_esclarecimento",
    "aguardando_terceiros",
    "resolvido",
  ],
  aguardando_esclarecimento: [
    "em_andamento",
    "aguardando_terceiros",
    "resolvido",
  ],
  aguardando_terceiros: [
    "em_andamento",
    "aguardando_esclarecimento",
    "resolvido",
  ],
  resolvido: ["encerrado", "reaberto"],
  encerrado: ["reaberto"],
  reaberto: [
    "em_andamento",
    "aguardando_esclarecimento",
    "aguardando_terceiros",
    "resolvido",
  ],
};
const label = (map: Record<string, string>, value: string) =>
  map[value] || value;
const get = (data: FormData, key: string) => String(data.get(key) || "");

export function WorkArea({
  userId,
  role,
  timezone,
  initialClient,
  hidden,
  focus,
  onArticle,
  creationRequest,
}: Props) {
  const [tab, setTab] = useState(initialClient ? "history" : "new");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [clients, setClients] = useState<{ id: string; name: string }[]>([]);
  const [people, setPeople] = useState<{ id: string; name: string }[]>([]);
  const [clientId, setClientId] = useState(initialClient || "");
  const [clientSearch, setClientSearch] = useState("");
  const [kind, setKind] = useState("finalizacao");
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [liveText, setLiveText] = useState("");
  const [originalText, setOriginalText] = useState("");
  const [captureBusy, setCaptureBusy] = useState(false);
  const [reviewedAudio, setReviewedAudio] = useState<Record<string, boolean>>(
    {},
  );
  const [occurred, setOccurred] = useState(
    localInput(new Date().toISOString(), timezone),
  );
  const [records, setRecords] = useState<Entry[]>([]);
  const [total, setTotal] = useState(0);
  const [confirmedTotal, setConfirmedTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [provisional, setProvisional] = useState(false);
  const [selected, setSelected] = useState<Entry | null>(null);
  const [versions, setVersions] = useState<
    { revision: number; snapshot: Entry; criado_em: string }[]
  >([]);
  const [checked, setChecked] = useState<string[]>([]);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const canOperate = role !== "tecnico" || ticket?.assignee_id === userId;
  const [ticketState, setTicketState] = useState("");
  const [notices, setNotices] = useState<Notice[]>([]);
  const [unread, setUnread] = useState(0);
  const [noticeError, setNoticeError] = useState(false);
  const creation = useRef<{
    key: string;
    body: unknown;
    recordId?: string;
  } | null>(null);
  const creationLock = useRef(false);
  const [pendingCreation, setPendingCreation] = useState(false);
  const [savedRecordId, setSavedRecordId] = useState("");
  useEffect(() => {
    if (!pendingCreation) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [pendingCreation]);
  const derivedKeys = useRef(new Map<string, string>());
  const formRef = useRef<HTMLFormElement>(null);
  const date = (value: string) =>
    new Intl.DateTimeFormat("pt-BR", {
      timeZone: timezone,
      dateStyle: "short",
      timeStyle: "short",
    }).format(new Date(value));

  async function perform(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await action();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : s.error);
    } finally {
      setBusy(false);
    }
  }
  async function refreshNotices() {
    const result = await request<{ unread: number; items: Notice[] }>(
      "/notifications",
    );
    setNotices(result.items);
    setUnread(result.unread);
    setNoticeError(false);
  }
  async function load(page = offset) {
    setChecked([]);
    if (tab === "reviews" || tab === "records") {
      const result = await request<PageResult<Entry>>(
        tab === "reviews"
          ? `/records/reviews?offset=${page}`
          : `/records?offset=${page}&limit=20`,
      );
      setRecords(result.items);
      setTotal(result.total);
    } else if (tab === "history") {
      if (!clientId) {
        setRecords([]);
        setTotal(0);
        return;
      }
      const result = await request<
        PageResult<Entry> & { confirmed_total: number }
      >(
        `/clients/${clientId}/history?include_provisional=${provisional}&offset=${page}&limit=20`,
      );
      setRecords(result.items);
      setTotal(result.total);
      setConfirmedTotal(result.confirmed_total);
    } else if (tab === "mine" || tab === "queue") {
      const result = await request<PageResult<Ticket>>(
        `/tickets?mine=${tab === "mine"}&offset=${page}&limit=20${ticketState ? `&status=${ticketState}` : ""}`,
      );
      setTickets(result.items);
      setTotal(result.total);
    }
    await refreshNotices();
  }
  useEffect(() => {
    let alive = true;
    const poll = () =>
      void request<{ unread: number; items: Notice[] }>("/notifications")
        .then((result) => {
          if (alive) {
            setNotices(result.items);
            setUnread(result.unread);
            setNoticeError(false);
          }
        })
        .catch(() => {
          if (alive) setNoticeError(true);
        });
    poll();
    const timer = setInterval(poll, 15000);
    void request<{ id: string; name: string }[]>("/assignment-options")
      .then((result) => {
        if (alive) setPeople(result);
      })
      .catch(() => {});
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);
  useEffect(() => {
    if (hidden) return;
    let alive = true;
    const target = initialClient || clientId;
    void request<PageResult<{ id: string; name: string }>>("/clients?limit=100")
      .then(async (result) => {
        if (target && !result.items.some((item) => item.id === target)) {
          result.items.push(
            await request<{ id: string; name: string }>(`/clients/${target}`),
          );
        }
        if (alive) setClients(result.items);
      })
      .catch((err) => {
        if (alive) setError(err instanceof ApiError ? err.message : s.error);
      });
    return () => {
      alive = false;
    };
  }, [hidden, initialClient]);
  useEffect(() => {
    if (!hidden) void perform(() => load(0));
  }, [tab, hidden, clientId, provisional, ticketState]);
  useEffect(() => {
    if (initialClient) {
      setClientId(initialClient);
      setTab("history");
      setOffset(0);
    }
  }, [initialClient]);
  useEffect(() => {
    if (!focus || hidden) return;
    void perform(async () => {
      if (focus.ticket) {
        setSelected(null);
        setTab("mine");
        await openTicket(focus.id);
      } else {
        setTicket(null);
        setTab("records");
        setSelected(await request<Entry>(`/records/${focus.id}`));
        setVersions([]);
      }
    });
  }, [focus, hidden]);

  useEffect(() => {
    if (!creationRequest) return;
    setTab("new");
    setSelected(null);
    setTicket(null);
    setOffset(0);
  }, [creationRequest]);

  function occurrence(data: FormData) {
    const explicit = get(data, "explicit_time");
    if (explicit) return explicit;
    const result = localToUtc(get(data, "ocorrido_em"), timezone);
    if (!result) throw new ApiError(422, s.invalidTime);
    return result;
  }
  function createSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (creationLock.current) return;
    const data = new FormData(event.currentTarget);
    const shouldSend =
      (event.nativeEvent as SubmitEvent).submitter?.getAttribute("value") !==
      "draft";
    void perform(async () => {
      creationLock.current = true;
      try {
        if (!creation.current) {
          creation.current = {
            key: crypto.randomUUID(),
            body: {
              client_id: clientId,
              type: kind,
              texto_original: get(data, "texto_original") || ms.audioOnly,
              ...(liveText ? { ditado_texto: liveText } : {}),
              ocorrido_em: occurrence(data),
              capturado_em: new Date().toISOString(),
              submit: shouldSend,
              category: get(data, "category"),
              system: get(data, "system"),
              ...(kind === "chamado"
                ? {
                    assignee_id: get(data, "assignee_id") || userId,
                    priority: get(data, "priority"),
                  }
                : {}),
            },
          };
        }
        let item = await request<Entry>(
          "/records",
          "POST",
          creation.current.body,
          { "Idempotency-Key": creation.current.key },
        );
        creation.current.recordId = item.id;
        setSavedRecordId(item.id);
        if (audioFile) {
          const sendAudio = async () => {
            const current = await request<Entry>(`/records/${item.id}`);
            return uploadFile<{ record: Entry }>(
              `/records/${item.id}/audio?revision=${current.revision}`,
              audioFile,
            );
          };
          try {
            item = (await sendAudio()).record;
          } catch (err) {
            // O worker pode avançar a revisão entre leitura e upload. Reenviar
            // os mesmos bytes uma vez preserva a deduplicação no servidor.
            if (!(err instanceof ApiError) || err.status !== 409) throw err;
            item = (await sendAudio()).record;
          }
        }
        creation.current = null;
        setPendingCreation(false);
        setSavedRecordId("");
        setAudioFile(null);
        setLiveText("");
        setOriginalText("");
        formRef.current?.reset();
        setSelected(item);
        setVersions([]);
        setTab("records");
        setMessage(s.saved);
      } catch (err) {
        if (
          creation.current &&
          (pendingCreation ||
            creation.current.recordId ||
            !(err instanceof ApiError) ||
            err.status >= 500)
        ) {
          setPendingCreation(true);
        } else {
          creation.current = null;
          setPendingCreation(false);
        }
        throw err;
      } finally {
        creationLock.current = false;
      }
    }).catch(() => {});
  }
  async function recordAction(
    item: Entry,
    action: string,
    reason = "",
    fields = {},
  ) {
    const value = await request<Entry>(`/records/${item.id}/actions`, "POST", {
      revision: item.revision,
      action,
      reason,
      audio_reviewed: !!reviewedAudio[item.id + ":" + item.revision],
      ...fields,
    });
    setSelected(value);
    setVersions([]);
    await load();
    setMessage(s.saved);
  }
  async function openTicket(identifier: string) {
    setTicket(await request<Ticket>(`/tickets/${identifier}`));
  }
  const timeFields = (value: string) => (
    <>
      <label>
        {s.occurred} · {timezone}
        <input
          type="datetime-local"
          name="ocorrido_em"
          required
          defaultValue={localInput(value, timezone)}
        />
      </label>
      <details>
        <summary>{s.explicitTime}</summary>
        <label>
          {s.explicitHint}
          <input name="explicit_time" maxLength={40} />
        </label>
      </details>
    </>
  );
  const personOptions = people.map((person) => (
    <option key={person.id} value={person.id}>
      {person.name}
    </option>
  ));
  const clientSelect = (
    <label>
      {s.client}
      <select
        required
        disabled={pendingCreation || busy}
        aria-label={s.client}
        value={clientId}
        onChange={(event) => {
          setClientId(event.target.value);
          creation.current = null;
        }}
      >
        <option value="">{s.select}</option>
        {clients.map((client) => (
          <option key={client.id} value={client.id}>
            {client.name}
          </option>
        ))}
      </select>
    </label>
  );
  const recordCard = (item: Entry) => (
    <article key={item.id} className="work-card">
      <h4>
        {item.client_name} · {label(s.kinds, item.type)}
      </h4>
      <p>{label(s.recordStates, item.status)}</p>
      <p>
        {s.author}: {item.author_name}
      </p>
      <p>
        {s.occurred}: {date(item.ocorrido_em)} · {s.reviewed}:{" "}
        {item.revisado_em ? date(item.revisado_em) : "—"}
      </p>
      <p>{item.texto_organizado || item.texto_original}</p>
      {item.status === "aguardando_revisao" && (
        <p>
          {s.age}: {Math.floor(item.age_seconds / 3600)} {s.hours}{" "}
          {item.age_seconds >= 86400 ? s.old : ""}
        </p>
      )}
      {tab === "reviews" && (
        <label>
          <input
            type="checkbox"
            aria-label={`${s.selectRecord} ${item.id}`}
            checked={checked.includes(item.id)}
            onChange={(event) =>
              setChecked((current) =>
                event.target.checked
                  ? [...current, item.id]
                  : current.filter((id) => id !== item.id),
              )
            }
          />
          {s.selectRecord}
        </label>
      )}
      <button
        disabled={busy}
        onClick={() => {
          setSelected(item);
          setVersions([]);
        }}
      >
        {s.details}
      </button>
    </article>
  );

  return (
    <section className="work-area" aria-label={s.title} hidden={hidden}>
      <h3>{s.title}</h3>
      <p>{s.noAutomation}</p>
      <p>
        {s.timezone}: {timezone}
      </p>
      {error && (
        <p role="alert" className="error">
          ! {error}
        </p>
      )}
      {message && <p role="status">{message}</p>}
      {noticeError && <p role="alert">{s.notifyError}</p>}
      <nav className="workspace-tabs" aria-label={s.title}>
        {[
          ["new", s.newRecord],
          ["records", s.myRecords],
          ["reviews", s.reviews],
          ["history", s.history],
          ["mine", s.myTickets],
          ["queue", s.queue],
          ["notifications", `${s.notifications} (${unread} ${s.unread})`],
          ["media", ms.config],
        ].map(([key, title]) => (
          <button
            key={key}
            aria-current={tab === key ? "page" : undefined}
            disabled={busy}
            onClick={() => {
              setTab(key);
              setOffset(0);
              setSelected(null);
              setTicket(null);
            }}
          >
            {title}
          </button>
        ))}
      </nav>
      {(tab === "new" || tab === "history") && (
        <>
          <form
            className="workspace-toolbar"
            onSubmit={(event) => {
              event.preventDefault();
              void perform(async () => {
                const result = await request<
                  PageResult<{ id: string; name: string }>
                >(
                  `/clients?limit=100&search=${encodeURIComponent(clientSearch)}`,
                );
                setClients(result.items);
              });
            }}
          >
            <label>
              {s.clientSearch}
              <input
                value={clientSearch}
                onChange={(e) => setClientSearch(e.target.value)}
              />
            </label>
            <button disabled={busy}>{s.clientSearch}</button>
          </form>
          {clientSelect}
        </>
      )}
      {tab === "new" && (
        <form
          ref={formRef}
          className="workspace-form"
          onSubmit={createSubmit}
          onChange={() => {
            if (!pendingCreation) creation.current = null;
          }}
        >
          <h4>{s.newRecord}</h4>
          {pendingCreation && <p role="alert">{ms.retryUpload}</p>}
          <fieldset
            disabled={busy || pendingCreation}
            className="record-fields"
          >
            <label>
              {s.destination}
              <select
                aria-label={s.destination}
                value={kind}
                onChange={(event) => setKind(event.target.value)}
              >
                {Object.entries(s.kinds).map(([key, value]) => (
                  <option key={key} value={key}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
            <label>
              {s.original}
              <textarea
                aria-label={s.original}
                required={!audioFile}
                name="texto_original"
                maxLength={20000}
                value={originalText}
                onChange={(event) => setOriginalText(event.target.value)}
              />
            </label>
            <label>
              {s.occurred} · {timezone}
              <input
                type="datetime-local"
                required
                name="ocorrido_em"
                value={occurred}
                onChange={(e) => setOccurred(e.target.value)}
              />
            </label>
            <details>
              <summary>{s.explicitTime}</summary>
              <label>
                {s.explicitHint}
                <input name="explicit_time" maxLength={40} />
              </label>
            </details>
            {kind === "chamado" && (
              <>
                <label>
                  {s.responsible}
                  <select
                    aria-label={s.responsible}
                    name="assignee_id"
                    defaultValue={userId}
                  >
                    {personOptions}
                  </select>
                </label>
                <label>
                  {s.priority}
                  <select
                    aria-label={s.priority}
                    name="priority"
                    defaultValue="normal"
                  >
                    {Object.entries(s.priorities).map(([key, value]) => (
                      <option key={key} value={key}>
                        {value}
                      </option>
                    ))}
                  </select>
                </label>
              </>
            )}
            <label>
              {s.category}
              <input name="category" maxLength={80} />
            </label>
            <label>
              {ins.system}
              <input name="system" maxLength={80} />
            </label>
            <AudioCapture
              file={audioFile}
              onFile={(file) => {
                setAudioFile(file);
                creation.current = null;
              }}
              live={liveText}
              onLive={(value) => {
                setLiveText(value);
                creation.current = null;
              }}
              onUseLive={() => {
                setOriginalText(liveText);
                creation.current = null;
              }}
              onBusy={setCaptureBusy}
            />
          </fieldset>
          <button disabled={busy || !clientId || captureBusy} value="send">
            {s.submit}
          </button>
          <button
            disabled={
              busy || pendingCreation || !clientId || captureBusy || !!audioFile
            }
            value="draft"
          >
            {s.draft}
          </button>
          {savedRecordId && pendingCreation && (
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                void perform(async () => {
                  const item = await request<Entry>(
                    `/records/${savedRecordId}`,
                  );
                  creation.current = null;
                  setPendingCreation(false);
                  setSavedRecordId("");
                  setAudioFile(null);
                  setLiveText("");
                  setOriginalText("");
                  setSelected(item);
                  setVersions([]);
                  setTab("records");
                })
              }
            >
              {ms.openSaved}
            </button>
          )}
        </form>
      )}
      {tab === "history" && (
        <>
          <label>
            <input
              type="checkbox"
              checked={provisional}
              onChange={(e) => setProvisional(e.target.checked)}
            />
            {s.includeProvisional}
          </label>
          <p>
            {s.confirmedTotal}: {confirmedTotal}
          </p>
          {clientId && <FilePanel ownerType="client" ownerId={clientId} />}
          {clientId && (
            <RelatedArticles clientId={clientId} onOpen={onArticle} />
          )}
        </>
      )}
      {["records", "reviews", "history"].includes(tab) && (
        <>
          <p>
            {s.total}: {total}
          </p>
          <button disabled={busy} onClick={() => void perform(() => load())}>
            {s.refresh}
          </button>
          {tab === "reviews" && (
            <button
              disabled={busy || !checked.length}
              onClick={() =>
                void perform(async () => {
                  await request("/records/reviews/confirm", "POST", {
                    items: records
                      .filter((item) => checked.includes(item.id))
                      .map((item) => ({
                        id: item.id,
                        revision: item.revision,
                        audio_reviewed:
                          !!reviewedAudio[item.id + ":" + item.revision],
                      })),
                  });
                  setSelected(null);
                  await load();
                  setMessage(s.saved);
                })
              }
            >
              {s.batch}
            </button>
          )}
          <div className="workspace-list">{records.map(recordCard)}</div>
          {!records.length && <p>{s.empty}</p>}
        </>
      )}
      {selected && (
        <article
          className="workspace-detail"
          key={selected.id + ":" + selected.revision}
        >
          <h4>
            {s.details} · {selected.client_name}
          </h4>
          <p>
            {label(s.recordStates, selected.status)} ·{" "}
            {selected.provisional ? s.provisional : s.official}
          </p>
          <p>
            {s.author}: {selected.author_name}
          </p>
          <p>
            {s.occurred}: {date(selected.ocorrido_em)}
          </p>
          <p>
            {s.sent}: {date(selected.enviado_em)}
          </p>
          {selected.revisado_em && (
            <p>
              {s.reviewed}: {date(selected.revisado_em)}
            </p>
          )}
          <p>
            {s.original}: {selected.texto_original}
          </p>
          {selected.texto_organizado && (
            <p>
              {s.edited}: {selected.texto_organizado}
            </p>
          )}
          {selected.article_id && (
            <p>
              {selected.article_status === "rascunho"
                ? s.articleDraft
                : ins.states[selected.article_status || "rascunho"]}
            </p>
          )}
          <button
            disabled={busy}
            onClick={() =>
              void perform(async () => {
                const item = await request<{ id: string }>(
                  "/knowledge/articles",
                  "POST",
                  { record_id: selected.id },
                );
                onArticle(item.id);
              })
            }
          >
            {ins.create}
          </button>
          {selected.template_version && (
            <p>
              {ms.templateVersion}: {selected.template_version}
            </p>
          )}
          <AudioReview
            key={selected.id + ":" + selected.revision}
            record={selected}
            isAuthor={selected.author_id === userId}
            onRecord={(value) => {
              setSelected(value);
              setRecords((current) =>
                current.map((item) => (item.id === value.id ? value : item)),
              );
            }}
            onAcknowledged={(value) =>
              setReviewedAudio((current) => ({
                ...current,
                [selected.id + ":" + selected.revision]: value,
              }))
            }
          />
          {selected.cancellation_reason && (
            <p>
              {s.reason}: {selected.cancellation_reason}
            </p>
          )}
          {selected.author_id === userId &&
            ["rascunho", "aguardando_revisao"].includes(selected.status) && (
              <>
                <form
                  className="workspace-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    const data = new FormData(event.currentTarget);
                    void perform(async () => {
                      const item = await request<Entry>(
                        `/records/${selected.id}`,
                        "PATCH",
                        {
                          revision: selected.revision,
                          texto_organizado: get(data, "texto_organizado"),
                          category: get(data, "category"),
                          system: get(data, "system"),
                          ...(get(data, "explicit_time") ||
                          get(data, "ocorrido_em") !==
                            localInput(selected.ocorrido_em, timezone)
                            ? { ocorrido_em: occurrence(data) }
                            : {}),
                        },
                      );
                      setSelected(item);
                      await load();
                      setMessage(s.saved);
                    });
                  }}
                >
                  <label>
                    {s.edited}
                    <textarea
                      aria-label={s.edited}
                      required
                      name="texto_organizado"
                      maxLength={20000}
                      defaultValue={
                        selected.texto_organizado || selected.texto_original
                      }
                    />
                  </label>
                  {timeFields(selected.ocorrido_em)}
                  <label>
                    {s.category}
                    <input
                      name="category"
                      maxLength={80}
                      defaultValue={selected.category}
                    />
                  </label>
                  <label>
                    {ins.system}
                    <input
                      name="system"
                      maxLength={80}
                      defaultValue={selected.system}
                    />
                  </label>
                  <button disabled={busy}>{s.save}</button>
                </form>
                {selected.status === "aguardando_revisao" &&
                  selected.type === "finalizacao" && (
                    <button
                      disabled={busy}
                      onClick={() =>
                        void perform(() => recordAction(selected, "confirmar"))
                      }
                    >
                      {s.confirm}
                    </button>
                  )}
                {selected.status === "aguardando_revisao" && (
                  <button
                    disabled={busy}
                    onClick={() =>
                      void perform(() => recordAction(selected, "devolver"))
                    }
                  >
                    {s.correction}
                  </button>
                )}
                {selected.status === "rascunho" &&
                  selected.type !== "chamado" && (
                    <button
                      disabled={busy}
                      onClick={() =>
                        void perform(() => recordAction(selected, "enviar"))
                      }
                    >
                      {s.submit}
                    </button>
                  )}
                {selected.status === "rascunho" &&
                  selected.type === "chamado" && (
                    <form
                      className="workspace-form"
                      onSubmit={(event) => {
                        event.preventDefault();
                        const data = new FormData(event.currentTarget);
                        void perform(() =>
                          recordAction(selected, "enviar", "", {
                            assignee_id: get(data, "assignee_id"),
                            priority: get(data, "priority"),
                            category: get(data, "category"),
                          }),
                        );
                      }}
                    >
                      <label>
                        {s.responsible}
                        <select
                          aria-label={s.responsible}
                          name="assignee_id"
                          defaultValue={userId}
                        >
                          {personOptions}
                        </select>
                      </label>
                      <label>
                        {s.priority}
                        <select
                          aria-label={s.priority}
                          name="priority"
                          defaultValue="normal"
                        >
                          {Object.entries(s.priorities).map(([key, value]) => (
                            <option key={key} value={key}>
                              {value}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        {s.category}
                        <input name="category" maxLength={80} />
                      </label>
                      <button disabled={busy}>{s.submit}</button>
                    </form>
                  )}
              </>
            )}
          {selected.author_id !== userId &&
            selected.type === "finalizacao" &&
            selected.status === "aguardando_revisao" && <p>{s.noReview}</p>}
          {selected.status !== "cancelado" &&
            !selected.ticket_id &&
            (selected.author_id === userId || role !== "tecnico") && (
              <form
                className="workspace-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  const data = new FormData(event.currentTarget);
                  void perform(() =>
                    recordAction(selected, "cancelar", get(data, "reason")),
                  );
                }}
              >
                <label>
                  {s.reason}
                  <input required name="reason" maxLength={2000} />
                </label>
                <button disabled={busy}>{s.cancel}</button>
              </form>
            )}
          <form
            className="workspace-form"
            onSubmit={(event) => {
              event.preventDefault();
              const data = new FormData(event.currentTarget);
              const target = get(data, "type");
              const intent = `${selected.id}:${selected.revision}:${target}`;
              if (!derivedKeys.current.has(intent))
                derivedKeys.current.set(intent, crypto.randomUUID());
              void perform(async () => {
                const item = await request<Entry>(
                  `/records/${selected.id}/derive`,
                  "POST",
                  { revision: selected.revision, type: target },
                  { "Idempotency-Key": derivedKeys.current.get(intent)! },
                );
                setSelected(item);
                setVersions([]);
                await load();
                setMessage(s.saved);
              });
            }}
          >
            <label>
              {s.deriveType}
              <select aria-label={s.deriveType} name="type">
                {Object.entries(s.kinds).map(([key, value]) => (
                  <option key={key} value={key}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
            <button disabled={busy}>{s.derive}</button>
          </form>
          <button
            disabled={busy}
            onClick={() =>
              void perform(async () =>
                setVersions(await request(`/records/${selected.id}/versions`)),
              )
            }
          >
            {s.versions}
          </button>
          {versions.map((version) => (
            <p key={version.revision}>
              {version.revision} · {date(version.criado_em)} ·{" "}
              {label(s.recordStates, version.snapshot.status)} ·{" "}
              {version.snapshot.texto_organizado ||
                version.snapshot.texto_original}
            </p>
          ))}
          {selected.ticket_id && (
            <button
              disabled={busy}
              onClick={() =>
                void perform(() => openTicket(selected.ticket_id!))
              }
            >
              {s.open}
            </button>
          )}
        </article>
      )}
      {(tab === "mine" || tab === "queue") && (
        <>
          <label>
            {s.status}
            <select
              aria-label={s.status}
              value={ticketState}
              onChange={(e) => {
                setTicketState(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">{s.all}</option>
              {Object.entries(s.ticketStates).map(([key, value]) => (
                <option key={key} value={key}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <button disabled={busy} onClick={() => void perform(() => load())}>
            {s.refresh}
          </button>
          <p>
            {s.total}: {total}
          </p>
          <div className="workspace-list">
            {tickets.map((item) => (
              <article key={item.id}>
                <h4>
                  {item.code} · {item.client_name}
                </h4>
                <p>
                  {label(s.ticketStates, item.status)} ·{" "}
                  {label(s.priorities, item.priority)}
                </p>
                <p>
                  {s.responsible}: {item.assignee_id_name}
                </p>
                <button
                  disabled={busy}
                  onClick={() => void perform(() => openTicket(item.id))}
                >
                  {s.open}
                </button>
              </article>
            ))}
          </div>
          {!tickets.length && <p>{s.empty}</p>}
        </>
      )}
      {ticket && (
        <article
          className="workspace-detail"
          key={ticket.id + ":" + ticket.revision}
        >
          <h4>{ticket.code}</h4>
          <button
            type="button"
            disabled={busy}
            onClick={() => void perform(() => openTicket(ticket.id))}
          >
            {s.refreshConversation}
          </button>
          <p>{ticket.description}</p>
          <p>
            {label(s.ticketStates, ticket.status)} ·{" "}
            {label(s.priorities, ticket.priority)}
          </p>
          <p>
            {s.openedBy}: {ticket.opened_by_name} · {s.responsible}:{" "}
            {ticket.assignee_id_name}
          </p>
          <p>
            {s.resolvedBy}: {ticket.resolved_by_name || "—"} · {s.closedBy}:{" "}
            {ticket.closed_by_name || "—"} · {s.reopens}: {ticket.reopen_count}
          </p>
          <FilePanel ownerType="ticket" ownerId={ticket.id} />
          <RelatedArticles
            key={ticket.id + ":" + ticket.revision}
            ticketId={ticket.id}
            onOpen={onArticle}
          />
          <form
            className="workspace-form"
            onSubmit={(event) => {
              event.preventDefault();
              const data = new FormData(event.currentTarget);
              void perform(async () => {
                const value = {
                  revision: ticket.revision,
                  ...(canOperate
                    ? {
                        assignee_id: get(data, "assignee_id"),
                        priority: get(data, "priority"),
                        category: get(data, "category"),
                        system: get(data, "system"),
                      }
                    : {}),
                  ...(get(data, "status")
                    ? { status: get(data, "status") }
                    : {}),
                };
                await request(`/tickets/${ticket.id}`, "PATCH", value);
                await openTicket(ticket.id);
                await load();
                setMessage(s.saved);
              });
            }}
          >
            <label>
              {s.responsible}
              <select
                aria-label={s.responsible}
                name="assignee_id"
                defaultValue={ticket.assignee_id}
                disabled={!canOperate}
              >
                {personOptions}
              </select>
            </label>
            <label>
              {s.priority}
              <select
                aria-label={s.priority}
                name="priority"
                defaultValue={ticket.priority}
                disabled={!canOperate}
              >
                {Object.entries(s.priorities).map(([key, value]) => (
                  <option key={key} value={key}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
            <label>
              {s.category}
              <input
                name="category"
                maxLength={80}
                defaultValue={ticket.category}
                disabled={!canOperate}
              />
            </label>
            <label>
              {ins.system}
              <input
                name="system"
                maxLength={80}
                defaultValue={ticket.system}
                disabled={!canOperate}
              />
            </label>
            <label>
              {s.status}
              <select aria-label={s.status} name="status">
                <option value="">{s.select}</option>
                {(transitions[ticket.status] || [])
                  .filter((state) =>
                    state === "encerrado"
                      ? ticket.opened_by === userId || role !== "tecnico"
                      : canOperate,
                  )
                  .map((state) => (
                    <option key={state} value={state}>
                      {label(s.ticketStates, state)}
                    </option>
                  ))}
              </select>
            </label>
            <button
              disabled={
                busy ||
                (role === "tecnico" &&
                  ticket.assignee_id !== userId &&
                  ticket.opened_by !== userId)
              }
            >
              {s.save}
            </button>
          </form>
          <h4>{s.conversation}</h4>
          {ticket.comments?.map((comment) => (
            <p key={comment.id}>
              {date(comment.criado_em)} · {comment.author_name} · {comment.text}
              <span> · {label(s.commentKinds, comment.kind)}</span>
              {comment.mentioned_user_ids.map((id) => (
                <span key={id}>
                  {" "}
                  · @
                  {people.find((person) => person.id === id)?.name || s.member}
                </span>
              ))}
            </p>
          ))}
          <form
            className="workspace-form"
            onSubmit={(event) => {
              event.preventDefault();
              const data = new FormData(event.currentTarget);
              const kind =
                (event.nativeEvent as SubmitEvent).submitter?.getAttribute(
                  "value",
                ) || "comentario";
              void perform(async () => {
                await request(`/tickets/${ticket.id}/comments`, "POST", {
                  revision: ticket.revision,
                  text: get(data, "text"),
                  kind,
                  mentioned_user_ids: data.getAll("mentions").map(String),
                });
                await openTicket(ticket.id);
                await load();
                setMessage(s.saved);
              });
            }}
          >
            <label>
              {s.text}
              <textarea
                aria-label={s.text}
                required
                name="text"
                maxLength={10000}
              />
            </label>
            <label>
              {s.mentions}
              <select aria-label={s.mentions} name="mentions" multiple>
                {people.map((person) => (
                  <option key={person.id} value={person.id}>
                    @{person.name}
                  </option>
                ))}
              </select>
            </label>
            <p>{s.mentionsHint}</p>
            <button value="comentario" disabled={busy}>
              {s.comment}
            </button>
            <button value="resposta" disabled={busy}>
              {s.reply}
            </button>
            {(ticket.assignee_id === userId || role !== "tecnico") &&
              !["resolvido", "encerrado", "aguardando_esclarecimento"].includes(
                ticket.status,
              ) && (
                <button value="esclarecimento" disabled={busy}>
                  {s.clarify}
                </button>
              )}
          </form>
          <h4>{s.events}</h4>
          {ticket.events?.map((event) => (
            <p key={event.id}>
              {date(event.ocorrido_em)} · {label(s.eventTypes, event.change)} ·{" "}
              {label(s.ticketStates, String(event.before.status || ""))} →{" "}
              {label(s.ticketStates, String(event.after.status || ""))}
            </p>
          ))}
          <h4>{s.intervals}</h4>
          {ticket.intervals?.map((interval) => (
            <p key={interval.id}>
              {label(s.ticketStates, interval.status)} ·{" "}
              {date(interval.entrada_em)} {s.until}{" "}
              {interval.saida_em ? date(interval.saida_em) : s.ongoing}
            </p>
          ))}
        </article>
      )}
      {tab === "media" && (
        <MediaConfiguration administrator={role === "administrador"} />
      )}
      {tab === "notifications" && (
        <>
          <button disabled={busy} onClick={() => void perform(refreshNotices)}>
            {s.refresh}
          </button>
          {notices.map((notice) => (
            <article key={notice.id}>
              <p>
                {label(s.notificationTypes, notice.type)} ·{" "}
                {date(notice.criado_em)}
              </p>
              <button
                disabled={busy}
                onClick={() =>
                  void perform(async () => {
                    await request(`/notifications/${notice.id}/read`, "POST");
                    if (notice.reference_type === "ticket")
                      await openTicket(notice.reference_id);
                    else {
                      setSelected(
                        await request<Entry>(`/records/${notice.reference_id}`),
                      );
                      setVersions([]);
                    }
                    await refreshNotices();
                  })
                }
              >
                {s.open}
              </button>
              {!notice.lida_em && (
                <button
                  disabled={busy}
                  onClick={() =>
                    void perform(async () => {
                      await request(`/notifications/${notice.id}/read`, "POST");
                      await refreshNotices();
                    })
                  }
                >
                  {s.markRead}
                </button>
              )}
            </article>
          ))}
        </>
      )}
      {["records", "reviews", "history", "mine", "queue"].includes(tab) && (
        <div className="workspace-toolbar">
          <button
            disabled={busy || offset === 0}
            onClick={() => {
              const page = Math.max(0, offset - (tab === "reviews" ? 50 : 20));
              setOffset(page);
              void perform(() => load(page));
            }}
          >
            {s.previous}
          </button>
          <button
            disabled={busy || offset + (tab === "reviews" ? 50 : 20) >= total}
            onClick={() => {
              const page = offset + (tab === "reviews" ? 50 : 20);
              setOffset(page);
              void perform(() => load(page));
            }}
          >
            {s.next}
          </button>
        </div>
      )}
    </section>
  );
}
