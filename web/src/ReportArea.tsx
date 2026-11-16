import { useEffect, useState, type FormEvent } from "react";
import { ApiError, request } from "./workspace-api";
import { insightStrings as s } from "./insight-strings";
import { workStrings as ws } from "./work-strings";

type Person = { id: string; name: string };
type Action = { actions: number; unique_tickets: number };
type Totals = Record<string, number | Action>;
type Sample = {
  median_seconds: number | null;
  p90_seconds: number | null;
  n: number;
  warning: string | null;
};
type Report = {
  scope: string;
  notice: string;
  interpretation_context: string;
  generated_at: string;
  period: { start_date: string; end_date: string; timezone: string };
  totals: Totals;
  comparison: {
    period: { start_date: string; end_date: string };
    totals: Totals;
  };
  people: ({ id: string; name: string } & Record<string, unknown>)[];
  series: {
    bucket: string;
    person_name: string;
    records: number;
    actions: Record<string, number>;
  }[];
  classifications: {
    person_name: string;
    category: string;
    system: string;
    records: number;
  }[];
  clients: { id: string; name: string; records: number }[];
  ticket_distribution: {
    category: string;
    system: string;
    priority: string;
    unique_tickets: number;
  }[];
  article_consultations: {
    article_id: string;
    title: string;
    consultations: number;
  }[];
  article_consultations_scope: string;
  times: {
    first_action: { gross: Sample; net: Sample };
    resolution: { gross: Sample; net: Sample };
    resolution_unique_tickets: number;
    excluded_samples: number;
  };
  queue: {
    id: string;
    code: string;
    client_name: string;
    assignee_name: string;
    priority: string;
    status: string;
    age_seconds: number;
  }[];
  workload: {
    date: string;
    records: number;
    active_tickets: number;
    pending_review_current_by_fact: number;
  }[];
  missing_history_tickets: number;
  history: {
    total: number;
    items: {
      id: string;
      client_name: string;
      author_name: string;
      type: string;
      status: string;
      ocorrido_em: string;
    }[];
  };
};
type Options = {
  people: Person[];
  teams: Person[];
  categories: string[];
  systems: string[];
};
type Team = {
  id: string;
  name: string;
  member_ids: string[];
  revision: number;
};
type Props = {
  role: string;
  timezone: string;
  onSource: (id: string, ticket?: boolean) => void;
  onArticle: (id: string) => void;
};
const totalsKeys = [
  "registered_records",
  "confirmed_finalizations",
  "awaiting_review",
  "other_provisional_finalizations",
  "cancelled_records",
];
const actionKeys = [
  "abriu",
  "assumiu",
  "comentou",
  "encaminhou",
  "movimentou",
  "resolveu",
  "encerrou",
  "reabriu",
  "aguardando_terceiros",
];
function count(value: unknown) {
  return typeof value === "number"
    ? value
    : value && typeof value === "object" && "actions" in value
      ? Number(value.actions)
      : 0;
}
function unique(value: unknown) {
  return value && typeof value === "object" && "unique_tickets" in value
    ? Number(value.unique_tickets)
    : 0;
}
const number = (value: number) =>
  new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(value);
const get = (data: FormData, key: string) => String(data.get(key) || "");

function Table({
  caption,
  headers,
  rows,
}: {
  caption: string;
  headers: string[];
  rows: React.ReactNode[][];
}) {
  return (
    <div
      className="table-scroll"
      tabIndex={0}
      role="region"
      aria-label={caption}
    >
      <table>
        <caption>{caption}</caption>
        <thead>
          <tr>
            {headers.map((label, index) => (
              <th key={index} scope="col">
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((cells, index) => (
            <tr key={index}>
              {cells.map((cell, column) => (
                <td key={column}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && <p>{s.empty}</p>}
    </div>
  );
}

export function ReportArea({ role, timezone, onSource, onArticle }: Props) {
  const [options, setOptions] = useState<Options>({
    people: [],
    teams: [],
    categories: [],
    systems: [],
  });
  const [clients, setClients] = useState<Person[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [clientSearch, setClientSearch] = useState("");
  const [filters, setFilters] = useState<Record<string, string>>({
    preset: "dia",
    start_date: "",
    end_date: "",
    client_id: "",
    responsible_id: "",
    team_id: "",
    category: "",
    system: "",
    granularity: "dia",
  });
  const [applied, setApplied] = useState<Record<string, string>>({
    preset: "dia",
  });
  const [value, setValue] = useState<Report | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [order, setOrder] = useState("name");
  const date = (instant: string) =>
    new Intl.DateTimeFormat("pt-BR", {
      timeZone: timezone,
      dateStyle: "short",
      timeStyle: "short",
    }).format(new Date(instant));
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
  async function load(next = filters) {
    const cleaned = Object.fromEntries(
      Object.entries(next).filter(([, value]) => value !== ""),
    );
    const report = await request<Report>(
      `/reports?${new URLSearchParams(cleaned)}`,
    );
    setValue(report);
    setApplied(cleaned);
  }
  async function loadOptions() {
    const [o, c] = await Promise.all([
      request<Options>("/reports/options"),
      request<{ items: Person[] }>("/clients?limit=100"),
    ]);
    setOptions(o);
    setClients(c.items);
    if (role === "administrador") setTeams(await request<Team[]>("/teams"));
  }
  useEffect(() => {
    let active = true;
    void Promise.all([
      request<Options>("/reports/options"),
      request<{ items: Person[] }>("/clients?limit=100"),
      request<Report>("/reports"),
      ...(role === "administrador" ? [request<Team[]>("/teams")] : []),
    ])
      .then(([o, c, r, t]) => {
        if (active) {
          setOptions(o as Options);
          setClients((c as { items: Person[] }).items);
          setValue(r as Report);
          if (t) setTeams(t as Team[]);
        }
      })
      .catch((err) => {
        if (active) setError(err instanceof ApiError ? err.message : s.error);
      });
    return () => {
      active = false;
    };
  }, [role]);
  async function download() {
    const csrf = await request<{ csrf_token: string }>("/auth/csrf");
    const response = await fetch("/api/v1/reports/export", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrf.csrf_token,
      },
      body: JSON.stringify(applied),
      signal: AbortSignal.timeout(60000),
    });
    if (!response.ok) {
      const body = await response.json();
      throw new ApiError(response.status, body.title);
    }
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url;
    link.download = "soldesk-relatorio.csv";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function teamSubmit(event: FormEvent<HTMLFormElement>, team?: Team) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    void perform(async () => {
      await request(
        team ? `/teams/${team.id}` : "/teams",
        team ? "PATCH" : "POST",
        {
          name: get(data, "name"),
          member_ids: data.getAll("member"),
          ...(team ? { revision: team.revision } : {}),
        },
      );
      await loadOptions();
      setMessage(s.saved);
    });
  }
  const people = value
    ? [...value.people].sort((a, b) =>
        order === "records"
          ? count(b.registered_records) - count(a.registered_records) ||
            a.name.localeCompare(b.name, "pt-BR")
          : a.name.localeCompare(b.name, "pt-BR"),
      )
    : [];
  const series = new Map<string, number>();
  value?.series.forEach((row) =>
    series.set(row.bucket, (series.get(row.bucket) || 0) + row.records),
  );
  const chart = [...series.entries()].slice(0, 31);
  const max = Math.max(1, ...chart.map(([, n]) => n));
  return (
    <section className="report-area" aria-label={s.reports}>
      <h3>{s.reports}</h3>
      <p>{s.notice}</p>
      <p>
        {s.timezone}: {timezone}
      </p>
      <p>{role === "tecnico" ? s.own : s.organization}</p>
      <p className="interpretation-context">{s.context}</p>
      {error && (
        <p role="alert" className="error">
          ! {error}
        </p>
      )}
      {message && <p role="status">{message}</p>}
      {busy && <p role="status">{s.loading}</p>}
      <form
        className="workspace-toolbar"
        onSubmit={(event) => {
          event.preventDefault();
          void perform(async () => {
            const result = await request<{ items: Person[] }>(
              `/clients?limit=100&search=${encodeURIComponent(clientSearch)}`,
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
            value={clientSearch}
            onChange={(e) => setClientSearch(e.target.value)}
          />
        </label>
        <button disabled={busy}>{s.clientSearch}</button>
      </form>
      <form
        className="workspace-form insight-filters"
        onSubmit={(event) => {
          event.preventDefault();
          void perform(() => load({ ...filters, history_offset: "0" }));
        }}
      >
        <label>
          {s.period}
          <select
            value={filters.preset}
            onChange={(e) => setFilters({ ...filters, preset: e.target.value })}
          >
            {Object.entries(s.presets).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>
        {filters.preset === "livre" &&
          [
            ["start_date", s.start],
            ["end_date", s.end],
          ].map(([key, label]) => (
            <label key={key}>
              {label}
              <input
                type="date"
                required
                value={filters[key]}
                onChange={(e) =>
                  setFilters({ ...filters, [key]: e.target.value })
                }
              />
            </label>
          ))}
        {[
          ["client_id", s.client, clients],
          ["responsible_id", s.person, options.people],
          ["team_id", s.team, options.teams],
        ].map(([key, label, list]) => (
          <label key={String(key)}>
            {String(label)}
            <select
              value={filters[String(key)]}
              onChange={(e) =>
                setFilters({ ...filters, [String(key)]: e.target.value })
              }
            >
              <option value="">{s.all}</option>
              {(list as Person[]).map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
        ))}
        {[
          ["category", s.category, options.categories],
          ["system", s.system, options.systems],
        ].map(([key, label, list]) => (
          <label key={String(key)}>
            {String(label)}
            <select
              value={filters[String(key)]}
              onChange={(e) =>
                setFilters({ ...filters, [String(key)]: e.target.value })
              }
            >
              <option value="">{s.all}</option>
              {(list as string[]).map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
        ))}
        <label>
          {s.granularity}
          <select
            value={filters.granularity}
            onChange={(e) =>
              setFilters({ ...filters, granularity: e.target.value })
            }
          >
            {Object.entries(s.granularities).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <button disabled={busy}>{s.apply}</button>
      </form>
      {value && (
        <>
          <p>
            {s.current}: {value.period.start_date} — {value.period.end_date} ·{" "}
            {date(value.generated_at)}
          </p>
          <p>
            {s.comparison}: {value.comparison.period.start_date} —{" "}
            {value.comparison.period.end_date}
          </p>
          <button disabled={busy} onClick={() => void perform(download)}>
            {s.export}
          </button>
          <div className="metric-cards">
            {totalsKeys.map((key) => (
              <article key={key}>
                <h4>{s.metrics[key]}</h4>
                <p className="metric-number">
                  {number(count(value.totals[key]))}
                </p>
                <p>
                  {s.prior}: {number(count(value.comparison.totals[key]))}
                </p>
              </article>
            ))}
          </div>
          <Table
            caption={s.current}
            headers={[s.actions, s.current, s.unique, s.prior]}
            rows={actionKeys.map((key) => [
              s.metrics[key],
              number(count(value.totals[key])),
              number(unique(value.totals[key])),
              number(count(value.comparison.totals[key])),
            ])}
          />
          {count(value.totals.registered_records) === 0 &&
            actionKeys.every((key) => count(value.totals[key]) === 0) && (
              <p>{s.empty}</p>
            )}
          <section aria-label={s.people}>
            <h4>{s.people}</h4>
            <p>{s.context}</p>
            <div className="workspace-toolbar">
              <button onClick={() => setOrder("name")}>{s.sortName}</button>
              <button onClick={() => setOrder("records")}>
                {s.sortRecords}
              </button>
            </div>
            <Table
              caption={s.people}
              headers={[
                s.name,
                s.metrics.registered_records,
                ...actionKeys.map(
                  (k) => `${s.metrics[k]} — ${s.actions} / ${s.unique}`,
                ),
              ]}
              rows={people.map((person) => [
                <button
                  key={person.id}
                  disabled={busy}
                  onClick={() => {
                    const next = { ...filters, responsible_id: person.id };
                    setFilters(next);
                    void perform(() => load(next));
                  }}
                >
                  {person.name}
                </button>,
                number(count(person.registered_records)),
                ...actionKeys.map(
                  (key) =>
                    `${number(count(person[key]))} / ${number(unique(person[key]))}`,
                ),
              ])}
            />
          </section>
          <section aria-label={s.chart}>
            <h4>{s.chart}</h4>
            <p>{s.chartLimit}</p>
            {chart.length > 0 && (
              <svg
                className="report-chart"
                role="img"
                aria-label={s.chart}
                viewBox={`0 0 640 ${chart.length * 32 + 24}`}
              >
                <title>{s.chart}</title>
                {chart.map(([day, n], index) => (
                  <g key={day}>
                    <text x="0" y={index * 32 + 20}>
                      {day}
                    </text>
                    <rect
                      x="125"
                      y={index * 32 + 5}
                      width={Math.max(1, (n / max) * 410)}
                      height="22"
                    />
                    <text x={140 + (n / max) * 410} y={index * 32 + 20}>
                      {n}
                    </text>
                  </g>
                ))}
              </svg>
            )}
            <Table
              caption={s.alternative}
              headers={[s.bucket, s.metrics.registered_records]}
              rows={[...series].map(([day, n]) => [day, number(n)])}
            />
          </section>
          <details>
            <summary>{s.distribution}</summary>
            <Table
              caption={s.distribution}
              headers={[
                s.bucket,
                s.name,
                s.metrics.registered_records,
                ...actionKeys.map((key) => s.metrics[key]),
              ]}
              rows={value.series.map((row) => [
                row.bucket,
                row.person_name,
                number(row.records),
                ...actionKeys.map((key) => number(row.actions[key] || 0)),
              ])}
            />
          </details>
          <section aria-label={s.times}>
            <h4>{s.times}</h4>
            <p>{s.timeHint}</p>
            <p>
              {s.resolutionUnique}: {value.times.resolution_unique_tickets} ·{" "}
              {s.excludedSamples}: {value.times.excluded_samples}
            </p>
            {(["first_action", "resolution"] as const).map((key) => (
              <div key={key}>
                <h5>{key === "first_action" ? s.firstAction : s.resolution}</h5>
                <Table
                  caption={
                    key === "first_action" ? s.firstAction : s.resolution
                  }
                  headers={[s.type, s.median, s.p90, s.n]}
                  rows={(["gross", "net"] as const).map((mode) => {
                    const sample = value.times[key][mode];
                    return [
                      mode === "gross" ? s.gross : s.net,
                      sample.median_seconds === null
                        ? s.noSample
                        : number(sample.median_seconds),
                      sample.p90_seconds === null
                        ? s.noSample
                        : number(sample.p90_seconds),
                      sample.n,
                    ];
                  })}
                />
                {value.times[key].gross.n < 5 && <p>ℹ {s.smallSample}</p>}
              </div>
            ))}
          </section>
          <section aria-label={s.classifications}>
            <h4>{s.classifications}</h4>
            <p>{s.noInference}</p>
            <Table
              caption={s.classifications}
              headers={[
                s.name,
                s.category,
                s.system,
                s.metrics.registered_records,
              ]}
              rows={value.classifications.map((row) => [
                row.person_name,
                row.category || s.noValue,
                row.system || s.noValue,
                row.records,
              ])}
            />
          </section>
          <section aria-label={s.ticketDistribution}>
            <h4>{s.ticketDistribution}</h4>
            <p>{s.ticketDistributionHint}</p>
            <Table
              caption={s.ticketDistribution}
              headers={[s.category, s.system, s.priority, s.unique]}
              rows={value.ticket_distribution.map((row) => [
                row.category || s.noValue,
                row.system || s.noValue,
                ws.priorities[row.priority as keyof typeof ws.priorities] ||
                  row.priority,
                row.unique_tickets,
              ])}
            />
          </section>
          <Table
            caption={s.clients}
            headers={[s.client, s.metrics.registered_records]}
            rows={value.clients.map((row) => [row.name, row.records])}
          />
          <section aria-label={s.articleViews}>
            <h4>{s.articleViews}</h4>
            <p>{s.viewScope}</p>
            <Table
              caption={s.articleViews}
              headers={[s.fields.title, s.views]}
              rows={value.article_consultations.map((row) => [
                <button
                  key={row.article_id}
                  onClick={() => onArticle(row.article_id)}
                >
                  {row.title}
                </button>,
                row.consultations,
              ])}
            />
          </section>
          <section aria-label={s.queueNow}>
            <h4>{s.queueNow}</h4>
            <Table
              caption={s.queueNow}
              headers={[
                s.code,
                s.client,
                s.assignee,
                s.priority,
                s.ticketState,
                s.age,
              ]}
              rows={value.queue.map((row) => [
                <button key={row.id} onClick={() => onSource(row.id, true)}>
                  {row.code}
                </button>,
                row.client_name,
                row.assignee_name,
                ws.priorities[row.priority as keyof typeof ws.priorities] ||
                  row.priority,
                ws.ticketStates[row.status as keyof typeof ws.ticketStates] ||
                  row.status,
                number(row.age_seconds / 3600),
              ])}
            />
          </section>
          <section aria-label={s.workload}>
            <h4>{s.workload}</h4>
            <p>{s.workloadHint}</p>
            {value.missing_history_tickets > 0 && (
              <p>
                ℹ {s.missingHistory}: {value.missing_history_tickets}
              </p>
            )}
            <Table
              caption={s.workload}
              headers={[
                s.occurred,
                s.metrics.registered_records,
                s.active,
                s.pendingNow,
              ]}
              rows={value.workload.map((row) => [
                row.date,
                row.records,
                row.active_tickets,
                row.pending_review_current_by_fact,
              ])}
            />
          </section>
          <section aria-label={s.history}>
            <h4>{s.history}</h4>
            <p>
              {s.total}: {value.history.total}
            </p>
            <Table
              caption={s.history}
              headers={[
                s.client,
                s.name,
                s.type,
                ws.status,
                s.occurred,
                s.openRecord,
              ]}
              rows={value.history.items.map((row) => [
                row.client_name,
                row.author_name,
                ws.kinds[row.type as keyof typeof ws.kinds] || row.type,
                ws.recordStates[row.status as keyof typeof ws.recordStates] ||
                  row.status,
                date(row.ocorrido_em),
                <button key={row.id} onClick={() => onSource(row.id)}>
                  {s.openRecord}
                </button>,
              ])}
            />
            <div className="workspace-toolbar">
              <button
                disabled={busy || Number(applied.history_offset || 0) === 0}
                onClick={() =>
                  void perform(() =>
                    load({
                      ...applied,
                      history_offset: String(
                        Math.max(0, Number(applied.history_offset || 0) - 100),
                      ),
                    }),
                  )
                }
              >
                {s.previous}
              </button>
              <button
                disabled={
                  busy ||
                  Number(applied.history_offset || 0) + 100 >=
                    value.history.total
                }
                onClick={() =>
                  void perform(() =>
                    load({
                      ...applied,
                      history_offset: String(
                        Number(applied.history_offset || 0) + 100,
                      ),
                    }),
                  )
                }
              >
                {s.next}
              </button>
            </div>
          </section>
        </>
      )}
      {role === "administrador" && (
        <details>
          <summary>{s.teams}</summary>
          <p>{s.teamHint}</p>
          {[null, ...teams].map((team) => (
            <form
              key={team ? `${team.id}:${team.revision}` : "new"}
              className="workspace-form"
              onSubmit={(event) => teamSubmit(event, team || undefined)}
            >
              <label>
                {s.teamName}
                <input
                  name="name"
                  required
                  maxLength={120}
                  defaultValue={team?.name || ""}
                />
              </label>
              <fieldset>
                <legend>{s.teamMembers}</legend>
                {options.people.map((person) => (
                  <label key={person.id}>
                    <input
                      type="checkbox"
                      name="member"
                      value={person.id}
                      defaultChecked={
                        team?.member_ids.includes(person.id) || false
                      }
                    />
                    {person.name}
                  </label>
                ))}
              </fieldset>
              <button disabled={busy}>
                {team ? s.saveTeam : s.createTeam}
              </button>
            </form>
          ))}
        </details>
      )}
    </section>
  );
}
