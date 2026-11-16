import { useEffect, useState, type FormEvent } from "react";
import { ApiError, request } from "./workspace-api";
import { insightStrings as s } from "./insight-strings";

type Client = { id: string; name: string };
export type Article = {
  id: string;
  record_id: string;
  revision: number;
  title: string;
  status: string;
  author_id: string;
  author_name: string;
  reviewer_name: string | null;
  client_id: string | null;
  client_name: string | null;
  template_version_id: string | null;
  template_version: number | null;
  atualizado_em: string;
  publicado_em: string | null;
  problem: string;
  context: string;
  confirmed_cause: string;
  procedure: string;
  result: string;
  text: string;
  keywords: string[];
  category: string;
  system: string;
  review_comment: string;
  can_publish: boolean;
  can_review: boolean;
  source_accessible: boolean;
  source_ticket_id: string | null;
  source_text?: string | null;
  warnings?: { kind: string }[];
  snippet?: string;
  highlights?: { start: number; end: number }[];
};
type Page = { items: Article[]; total: number };
type Policy = {
  publisher_roles: string[];
  allow_self_publish: boolean;
  can_review: boolean;
};
type Version = {
  revision: number;
  actor_name: string | null;
  criado_em: string;
  diff: { field: string; before: unknown; after: unknown }[];
};
type Props = {
  userId: string;
  role: string;
  timezone: string;
  initialArticle?: string;
  initialClient?: string;
  onSource: (id: string, ticket?: boolean) => void;
};
const field = (data: FormData, key: string) => String(data.get(key) || "");

export function ArticleSnippet({ article }: { article: Article }) {
  const value = article.snippet || "";
  const mark = article.highlights?.[0];
  return (
    <p>
      {mark ? (
        <>
          {value.slice(0, mark.start)}
          <mark>{value.slice(mark.start, mark.end)}</mark>
          {value.slice(mark.end)}
        </>
      ) : (
        value
      )}
    </p>
  );
}

export function RelatedArticles({
  ticketId,
  clientId,
  onOpen,
}: {
  ticketId?: string;
  clientId?: string;
  onOpen: (id: string) => void;
}) {
  const [items, setItems] = useState<Article[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    setItems([]);
    setError("");
    setLoading(true);
    void request<Page>(
      ticketId
        ? `/tickets/${ticketId}/suggestions`
        : `/knowledge/search?client_id=${clientId}`,
    )
      .then((value) => {
        if (active) setItems(value.items);
      })
      .catch(() => {
        if (active) setError(s.error);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [ticketId, clientId]);
  return (
    <section
      aria-label={ticketId ? s.related : s.clientArticles}
      className="insight-section"
    >
      <h4>{ticketId ? s.related : s.clientArticles}</h4>
      {ticketId && <p>{s.suggestion}</p>}
      {error && <p role="alert">! {error}</p>}
      {loading && <p role="status">{s.loading}</p>}
      {!items.length && !error && !loading && <p>{s.empty}</p>}
      {items.map((item) => (
        <article key={item.id}>
          <h5>{item.title}</h5>
          <p>
            {item.category || s.noValue} · {item.system || s.noValue} ·{" "}
            {item.client_name || s.general}
          </p>
          <button onClick={() => onOpen(item.id)}>{s.open}</button>
        </article>
      ))}
    </section>
  );
}

export function KnowledgeArea({
  userId,
  role,
  timezone,
  initialArticle,
  initialClient,
  onSource,
}: Props) {
  const [tab, setTab] = useState("search");
  const [items, setItems] = useState<Article[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Article | null>(null);
  const [versions, setVersions] = useState<Version[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [clientQuery, setClientQuery] = useState("");
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [sources, setSources] = useState<
    { id: string; client_name: string; ocorrido_em: string }[]
  >([]);
  const [filters, setFilters] = useState({
    q: "",
    category: "",
    system: "",
    client_id: initialClient || "",
    status: "publicado",
    start_date: "",
    end_date: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [human, setHuman] = useState(false);
  const [warnings, setWarnings] = useState(false);
  const date = (value: string) =>
    new Intl.DateTimeFormat("pt-BR", {
      timeZone: timezone,
      dateStyle: "short",
      timeStyle: "short",
    }).format(new Date(value));
  async function perform(task: () => Promise<void>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await task();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : s.error);
    } finally {
      setBusy(false);
    }
  }
  async function load(page = 0) {
    let value: Page;
    if (tab === "search") {
      const params = new URLSearchParams({ offset: String(page) });
      Object.entries(filters).forEach(([key, value]) => {
        if (value) params.set(key, value);
      });
      value = await request<Page>(`/knowledge/search?${params}`);
    } else
      value = await request<Page>(
        `/knowledge/drafts?queue=${tab === "queue"}&offset=${page}`,
      );
    setItems(value.items);
    setTotal(value.total);
    setOffset(page);
  }
  async function open(id: string) {
    const value = await request<Article>(`/knowledge/articles/${id}`);
    setSelected(value);
    setVersions([]);
    setHuman(false);
    setWarnings(false);
  }
  useEffect(() => {
    let alive = true;
    void Promise.all([
      request<Policy>("/knowledge/policy"),
      request<{ items: Client[] }>("/clients?limit=100"),
      request<{
        items: { id: string; client_name: string; ocorrido_em: string }[];
      }>("/records?limit=100&mine=true"),
    ])
      .then(([p, c, r]) => {
        if (alive) {
          setPolicy(p);
          setClients(c.items);
          setSources(r.items);
        }
      })
      .catch(() => {
        if (alive) setError(s.error);
      });
    return () => {
      alive = false;
    };
  }, []);
  useEffect(() => {
    void perform(() => load(0));
  }, [tab]);
  useEffect(() => {
    if (initialArticle) void perform(() => open(initialArticle));
  }, [initialArticle]);
  async function act(action: string, comment = "") {
    if (!selected) return;
    const value = await request<Article>(
      `/knowledge/articles/${selected.id}/actions`,
      "POST",
      {
        revision: selected.revision,
        action,
        comment,
        human_reviewed: human,
        warnings_reviewed: warnings,
      },
    );
    setSelected(value);
    setHuman(false);
    setWarnings(false);
    setVersions([]);
    setMessage(s.saved);
    await load(offset);
  }
  function edit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    void perform(async () => {
      if (!selected) return;
      const body: Record<string, unknown> = { revision: selected.revision };
      Object.keys(s.fields)
        .filter((k) => !["status", "review_comment"].includes(k))
        .forEach((key) => {
          body[key] =
            key === "keywords"
              ? field(data, key)
                  .split("\n")
                  .map((v) => v.trim())
                  .filter(Boolean)
              : key === "client_id"
                ? field(data, key) || null
                : field(data, key);
        });
      setSelected(
        await request<Article>(
          `/knowledge/articles/${selected.id}`,
          "PATCH",
          body,
        ),
      );
      setMessage(s.saved);
      setVersions([]);
      await load(offset);
    });
  }
  const clientOptions = (
    <>
      <option value="">{s.general}</option>
      {(selected?.client_id &&
      !clients.some((client) => client.id === selected.client_id)
        ? [
            ...clients,
            { id: selected.client_id, name: selected.client_name || s.client },
          ]
        : clients
      ).map((client) => (
        <option key={client.id} value={client.id}>
          {client.name}
        </option>
      ))}
    </>
  );
  const editable =
    selected?.author_id === userId &&
    ["rascunho", "devolvido"].includes(selected.status);
  return (
    <section className="knowledge-area" aria-label={s.knowledge}>
      <h3>{s.knowledge}</h3>
      <p>{s.noAuto}</p>
      {error && (
        <p role="alert" className="error">
          ! {error}
        </p>
      )}
      {message && <p role="status">{message}</p>}
      {busy && <p role="status">{s.loading}</p>}
      <nav className="workspace-tabs" aria-label={s.knowledge}>
        {[
          ["search", s.published],
          ["drafts", s.drafts],
          ...(policy?.can_review ? [["queue", s.queue]] : []),
        ].map(([key, label]) => (
          <button
            key={key}
            disabled={busy}
            onClick={() => {
              setTab(key);
              setSelected(null);
              setOffset(0);
            }}
          >
            {label}
          </button>
        ))}
      </nav>
      <form
        className="workspace-toolbar"
        onSubmit={(event) => {
          event.preventDefault();
          void perform(async () => {
            const result = await request<{ items: Client[] }>(
              `/clients?limit=100&search=${encodeURIComponent(clientQuery)}`,
            );
            setClients((previous) => [
              ...result.items,
              ...previous.filter(
                (client) =>
                  client.id === filters.client_id &&
                  !result.items.some((item) => item.id === client.id),
              ),
            ]);
          });
        }}
      >
        <label>
          {s.clientSearch}
          <input
            value={clientQuery}
            onChange={(e) => setClientQuery(e.target.value)}
          />
        </label>
        <button disabled={busy}>{s.clientSearch}</button>
      </form>
      {tab === "search" && (
        <form
          className="workspace-form insight-filters"
          onSubmit={(event) => {
            event.preventDefault();
            void perform(() => load(0));
          }}
        >
          {[
            ["q", s.query],
            ["category", s.category],
            ["system", s.system],
            ["start_date", s.start],
            ["end_date", s.end],
          ].map(([key, label]) => (
            <label key={key}>
              {label}
              <input
                name={key}
                type={key.endsWith("date") ? "date" : "text"}
                value={filters[key as keyof typeof filters]}
                maxLength={key === "q" ? 200 : 80}
                onChange={(e) =>
                  setFilters({ ...filters, [key]: e.target.value })
                }
              />
            </label>
          ))}
          <label>
            {s.client}
            <select
              value={filters.client_id}
              onChange={(e) =>
                setFilters({ ...filters, client_id: e.target.value })
              }
            >
              {clientOptions}
            </select>
          </label>
          <label>
            {s.status}
            <select
              value={filters.status}
              onChange={(e) =>
                setFilters({ ...filters, status: e.target.value })
              }
            >
              <option value="publicado">{s.published}</option>
              <option value="arquivado">{s.archived}</option>
            </select>
          </label>
          <button disabled={busy}>{s.search}</button>
        </form>
      )}
      <p>
        {s.total}: {total}
      </p>
      <div className="workspace-list">
        {items.map((item) => (
          <article key={item.id}>
            <h4>{item.title || s.states.rascunho}</h4>
            <p>
              {s.states[item.status]} · {item.category || s.noValue} ·{" "}
              {item.system || s.noValue} · {item.client_name || s.general}
            </p>
            <ArticleSnippet article={item} />
            {item.source_accessible && (
              <a
                href={`#registro=${item.record_id}`}
                onClick={(event) => {
                  event.preventDefault();
                  onSource(item.record_id);
                }}
              >
                {s.source}
              </a>
            )}
            <button
              disabled={busy}
              onClick={() => void perform(() => open(item.id))}
            >
              {s.open}
            </button>
          </article>
        ))}
      </div>
      {!items.length && !busy && <p>{s.empty}</p>}
      <div className="workspace-toolbar">
        <button
          disabled={busy || offset === 0}
          onClick={() => void perform(() => load(Math.max(0, offset - 20)))}
        >
          {s.previous}
        </button>
        <button
          disabled={busy || offset + 20 >= total}
          onClick={() => void perform(() => load(offset + 20))}
        >
          {s.next}
        </button>
      </div>
      <details>
        <summary>{s.create}</summary>
        <p>{s.sourceHelp}</p>
        <form
          className="workspace-form"
          onSubmit={(event) => {
            event.preventDefault();
            const data = new FormData(event.currentTarget);
            void perform(async () => {
              const item = await request<Article>(
                "/knowledge/articles",
                "POST",
                { record_id: field(data, "record_id") },
              );
              await open(item.id);
              await load(0);
            });
          }}
        >
          <label>
            {s.chooseSource}
            <select required name="record_id">
              <option value="">{s.noValue}</option>
              {sources.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.client_name} · {date(item.ocorrido_em)}
                </option>
              ))}
            </select>
          </label>
          <button disabled={busy}>{s.create}</button>
        </form>
      </details>
      {selected && (
        <article
          className="workspace-detail"
          aria-label={s.open}
          key={selected.id + ":" + selected.revision}
        >
          <h4>{selected.title || s.states.rascunho}</h4>
          <p>
            {s.states[selected.status]} · {s.version} {selected.revision}
          </p>
          <p>
            {s.author}: {selected.author_name} · {s.reviewer}:{" "}
            {selected.reviewer_name || s.noValue}
          </p>
          <p>
            {s.updated}: {date(selected.atualizado_em)}
            {selected.publicado_em &&
              ` · ${s.publishedAt}: ${date(selected.publicado_em)}`}
          </p>
          <p>
            {s.template}: {selected.template_version || s.noValue}
          </p>
          {selected.review_comment && (
            <p className="review-warning">↩ {selected.review_comment}</p>
          )}
          <div className="review-warning">
            {selected.warnings?.map((warning, index) => (
              <p key={index}>{s.warnings[warning.kind] || s.warningReview}</p>
            ))}
          </div>
          {selected.source_accessible ? (
            <div className="workspace-toolbar">
              <a
                href={`#registro=${selected.record_id}`}
                onClick={(event) => {
                  event.preventDefault();
                  onSource(selected.record_id);
                }}
              >
                {s.source}
              </a>
              {selected.source_ticket_id && (
                <a
                  href={`#chamado=${selected.source_ticket_id}`}
                  onClick={(event) => {
                    event.preventDefault();
                    onSource(selected.source_ticket_id!, true);
                  }}
                >
                  {s.sourceTicket}
                </a>
              )}
            </div>
          ) : (
            <p>{s.inaccessibleSource}</p>
          )}
          {selected.source_text && (
            <details>
              <summary>{s.sourceText}</summary>
              <p className="preserved-text">{selected.source_text}</p>
            </details>
          )}
          {editable ? (
            <form className="workspace-form" onSubmit={edit}>
              {Object.entries(s.fields)
                .filter(
                  ([key]) =>
                    !["status", "review_comment", "client_id"].includes(key),
                )
                .map(([key, label]) => (
                  <label key={key}>
                    {label}
                    {["title", "category", "system"].includes(key) ? (
                      <input
                        name={key}
                        defaultValue={String(
                          selected[key as keyof Article] || "",
                        )}
                        required={key === "title"}
                        maxLength={key === "title" ? 200 : 80}
                      />
                    ) : (
                      <textarea
                        name={key}
                        defaultValue={
                          key === "keywords"
                            ? selected.keywords.join("\n")
                            : String(selected[key as keyof Article] || "")
                        }
                        placeholder={
                          key === "confirmed_cause" ? s.noCause : undefined
                        }
                        maxLength={
                          key === "text"
                            ? 20000
                            : key === "procedure"
                              ? 15000
                              : key === "confirmed_cause"
                                ? 5000
                                : 10000
                        }
                      />
                    )}
                  </label>
                ))}
              <label>
                {s.scope}
                <select
                  name="client_id"
                  defaultValue={selected.client_id || ""}
                >
                  {clientOptions}
                </select>
              </label>
              <p>{s.scopeHint}</p>
              <button disabled={busy}>{s.save}</button>
            </form>
          ) : (
            <dl className="article-fields">
              {Object.entries(s.fields)
                .filter(
                  ([key]) =>
                    !["status", "review_comment", "client_id"].includes(key),
                )
                .map(([key, label]) => (
                  <div key={key}>
                    <dt>{label}</dt>
                    <dd className="preserved-text">
                      {key === "keywords"
                        ? selected.keywords.join(", ")
                        : String(
                            selected[key as keyof Article] ||
                              (key === "confirmed_cause"
                                ? s.noCause
                                : s.noValue),
                          )}
                    </dd>
                  </div>
                ))}
              <div>
                <dt>{s.scope}</dt>
                <dd>{selected.client_name || s.general}</dd>
              </div>
            </dl>
          )}
          <div className="workspace-toolbar">
            {editable && (
              <button
                disabled={busy}
                onClick={() => void perform(() => act("enviar"))}
              >
                {s.submit}
              </button>
            )}
            {selected.status === "arquivado" &&
              selected.author_id === userId && (
                <button
                  disabled={busy}
                  onClick={() => void perform(() => act("reabrir"))}
                >
                  {s.reopen}
                </button>
              )}
          </div>
          {selected.status === "aguardando_revisao" && selected.can_publish && (
            <div className="workspace-form">
              <label>
                <input
                  type="checkbox"
                  checked={human}
                  onChange={(e) => setHuman(e.target.checked)}
                />
                {s.humanReview}
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={warnings}
                  onChange={(e) => setWarnings(e.target.checked)}
                />
                {s.warningReview}
              </label>
              <button
                disabled={busy || !human || !warnings}
                onClick={() => void perform(() => act("publicar"))}
              >
                {s.publish}
              </button>
            </div>
          )}
          {((selected.status === "aguardando_revisao" && selected.can_review) ||
            (selected.status === "publicado" && policy?.can_review)) && (
            <form
              className="workspace-form"
              onSubmit={(event) => {
                event.preventDefault();
                const data = new FormData(event.currentTarget);
                void perform(() =>
                  act(
                    selected.status === "publicado" ? "arquivar" : "devolver",
                    field(data, "comment"),
                  ),
                );
              }}
            >
              <label>
                {s.reviewComment}
                <textarea name="comment" required maxLength={3000} />
              </label>
              <button disabled={busy}>
                {selected.status === "publicado" ? s.archive : s.return}
              </button>
            </form>
          )}
          <button
            disabled={busy}
            onClick={() =>
              void perform(async () =>
                setVersions(
                  await request<Version[]>(
                    `/knowledge/articles/${selected.id}/versions`,
                  ),
                ),
              )
            }
          >
            {s.versions}
          </button>
          {versions.map((version) => (
            <details key={version.revision}>
              <summary>
                {s.version} {version.revision} ·{" "}
                {version.actor_name || s.migration} · {date(version.criado_em)}
              </summary>
              {version.diff.map((diff) => (
                <div key={diff.field}>
                  <h5>{s.fields[diff.field] || diff.field}</h5>
                  <p className="preserved-text">
                    {s.before}:{" "}
                    {Array.isArray(diff.before)
                      ? diff.before.join(", ")
                      : String(diff.before ?? s.noValue)}
                  </p>
                  <p className="preserved-text">
                    {s.after}:{" "}
                    {Array.isArray(diff.after)
                      ? diff.after.join(", ")
                      : String(diff.after ?? s.noValue)}
                  </p>
                </div>
              ))}
            </details>
          ))}
        </article>
      )}
      {role === "administrador" && policy && (
        <details>
          <summary>{s.policy}</summary>
          <p>{s.selfOff}</p>
          <form
            key={JSON.stringify(policy)}
            className="workspace-form"
            onSubmit={(event) => {
              event.preventDefault();
              const data = new FormData(event.currentTarget);
              void perform(async () => {
                setPolicy(
                  await request<Policy>("/knowledge/policy", "PATCH", {
                    publisher_roles: data.getAll("role"),
                    allow_self_publish: data.has("self"),
                  }),
                );
                setMessage(s.saved);
              });
            }}
          >
            <fieldset>
              <legend>{s.publisherRoles}</legend>
              {Object.entries(s.roles).map(([key, label]) => (
                <label key={key}>
                  <input
                    type="checkbox"
                    name="role"
                    value={key}
                    defaultChecked={policy.publisher_roles.includes(key)}
                  />
                  {label}
                </label>
              ))}
            </fieldset>
            <label>
              <input
                type="checkbox"
                name="self"
                defaultChecked={policy.allow_self_publish}
              />
              {s.selfPublish}
            </label>
            <button disabled={busy}>{s.save}</button>
          </form>
        </details>
      )}
    </section>
  );
}
