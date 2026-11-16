import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { ApiError, request } from "./workspace-api";
import { workspaceStrings as s } from "./strings";
import { WorkArea } from "./WorkArea";
import { workStrings } from "./work-strings";

type Organization = {
  id: string;
  name: string;
  timezone: string;
  slug: string;
  settings: Record<string, boolean>;
};
type Profile = {
  id: string;
  name: string;
  email: string;
  role: string;
  organization_id: string;
  organizations: Organization[];
  must_change_password: boolean;
};
type ExternalRef = { provider: string; identifier: string; label: string };
type Client = {
  id: string;
  name: string;
  nickname: string;
  phone: string;
  email: string;
  notes: string;
  situation: string;
  criado_em: string;
  external_refs: ExternalRef[];
};
type Member = {
  id: string;
  name: string;
  email: string;
  role: string;
  situation: string;
};
type Invitation = {
  id: string;
  email: string;
  role: string;
  expira_em: string;
  usado_em: string | null;
};
type Audit = { id: string; action: string; ocorrido_em: string };

const formValue = (form: FormData, key: string) => String(form.get(key) || "");

function Field({
  label,
  name,
  value = "",
  type = "text",
  required = true,
  maxLength = 160,
}: {
  label: string;
  name: string;
  value?: string;
  type?: string;
  required?: boolean;
  maxLength?: number;
}) {
  return (
    <label>
      {label}
      <input
        name={name}
        type={type}
        defaultValue={value}
        required={required}
        maxLength={maxLength}
        autoComplete={type === "password" ? "off" : undefined}
      />
    </label>
  );
}
function Roles({ value = "tecnico" }: { value?: string }) {
  return (
    <label>
      {s.role}
      <select name="role" defaultValue={value}>
        <option value="tecnico">{s.technician}</option>
        <option value="gestor">{s.manager}</option>
        <option value="administrador">{s.administrator}</option>
      </select>
    </label>
  );
}
function Situation({ value = "ativo" }: { value?: string }) {
  return (
    <label>
      {s.situation}
      <select name="situation" defaultValue={value}>
        <option value="ativo">{s.active}</option>
        <option value="inativo">{s.inactive}</option>
      </select>
    </label>
  );
}

export function Workspace() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [tab, setTab] = useState("clients");
  const [workClient, setWorkClient] = useState<string | undefined>();
  const [authTab, setAuthTab] = useState(
    location.hash.startsWith("#convite=") ? "invitation" : "login",
  );
  const [signup, setSignup] = useState(false);
  const [clients, setClients] = useState<Client[]>([]);
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [editor, setEditor] = useState<Client | "new" | null>(null);
  const [selected, setSelected] = useState<Client | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [audit, setAudit] = useState<Audit[]>([]);
  const [oneTime, setOneTime] = useState("");
  const [copied, setCopied] = useState(false);
  const organization = profile?.organizations.find(
    (o) => o.id === profile.organization_id,
  );
  const date = (value: string) =>
    new Intl.DateTimeFormat("pt-BR", {
      dateStyle: "short",
      timeStyle: "short",
      timeZone: organization?.timezone || "America/Sao_Paulo",
    }).format(new Date(value));

  async function loadProfile() {
    setProfile(await request<Profile>("/me"));
  }
  async function loadClients(query = search, page = offset) {
    const result = await request<{ items: Client[]; total: number }>(
      `/clients?search=${encodeURIComponent(query)}&offset=${page}&limit=10`,
    );
    setClients(result.items);
    setTotal(result.total);
  }
  async function loadTeam() {
    const list = await request<Member[]>("/memberships");
    setMembers(list);
    setAudit(await request<Audit[]>("/audit-events"));
    if (profile?.role === "administrador")
      setInvitations(await request<Invitation[]>("/invitations"));
  }
  async function perform(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await action();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : s.error);
      if (err instanceof ApiError && err.status === 401) setProfile(null);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    void request<{ signup_enabled: boolean }>("/auth/config")
      .then((r) => setSignup(r.signup_enabled))
      .catch(() => {});
    void request<Profile>("/me")
      .then(setProfile)
      .catch((err) => {
        if (!(err instanceof ApiError && err.status === 401))
          setError(err instanceof ApiError ? err.message : s.error);
      })
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => {
    if (profile && !profile.must_change_password) {
      if (tab !== "work") setWorkClient(undefined);
      setClients([]);
      setMembers([]);
      setSelected(null);
      setEditor(null);
      setOneTime("");
      void perform(async () => {
        if (tab === "clients") await loadClients();
        if (tab === "team") await loadTeam();
      });
    }
    // Recarregar somente quando o contexto autenticado ou a aba mudar.
  }, [profile?.organization_id, profile?.must_change_password, tab]);

  function authSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    void perform(async () => {
      const common = {
        email: formValue(data, "email"),
        password: formValue(data, "password"),
      };
      if (authTab === "signup")
        await request("/organizations", "POST", {
          ...common,
          name: formValue(data, "name"),
          organization_name: formValue(data, "organization_name"),
          slug: formValue(data, "slug"),
          timezone: formValue(data, "timezone"),
        });
      else if (authTab === "invitation") {
        await request("/invitations/accept", "POST", {
          ...common,
          name: formValue(data, "name"),
          token: formValue(data, "token"),
        });
        history.replaceState(null, "", location.pathname);
      } else await request("/auth/login", "POST", common);
      await loadProfile();
    });
  }
  function passwordSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const form = event.currentTarget;
    void perform(async () => {
      await request("/auth/password", "POST", {
        current_password: formValue(data, "current_password"),
        new_password: formValue(data, "new_password"),
      });
      form.reset();
      await loadProfile();
      setMessage(s.saved);
    });
  }
  const passwordForm = (
    <form className="workspace-form" onSubmit={passwordSubmit}>
      <h3>{s.changePassword}</h3>
      <Field
        label={s.currentPassword}
        name="current_password"
        type="password"
        maxLength={128}
      />
      <Field
        label={s.newPassword}
        name="new_password"
        type="password"
        maxLength={128}
      />
      <button disabled={busy}>{s.save}</button>
    </form>
  );
  let content: ReactNode;
  if (loading) content = <p>{s.loading}</p>;
  else if (!profile)
    content = (
      <>
        <nav className="workspace-tabs" aria-label={s.login}>
          <button type="button" onClick={() => setAuthTab("login")}>
            {s.login}
          </button>
          <button type="button" onClick={() => setAuthTab("invitation")}>
            {s.invitation}
          </button>
          {signup && (
            <button type="button" onClick={() => setAuthTab("signup")}>
              {s.signup}
            </button>
          )}
        </nav>
        <form className="workspace-form" onSubmit={authSubmit} key={authTab}>
          <h3>
            {authTab === "signup"
              ? s.signup
              : authTab === "invitation"
                ? s.invitation
                : s.login}
          </h3>
          {authTab !== "login" && <Field label={s.name} name="name" />}
          <Field label={s.email} name="email" type="email" maxLength={254} />
          <Field
            label={s.password}
            name="password"
            type="password"
            maxLength={128}
          />
          {authTab === "invitation" && (
            <Field
              label={s.token}
              name="token"
              value={
                new URLSearchParams(location.hash.slice(1)).get("convite") || ""
              }
              maxLength={128}
            />
          )}
          {authTab === "signup" && (
            <>
              <Field label={s.organizationName} name="organization_name" />
              <Field label={s.slug} name="slug" maxLength={80} />
              <Field
                label={s.timezone}
                name="timezone"
                value="America/Sao_Paulo"
                maxLength={80}
              />
            </>
          )}
          <button disabled={busy}>{busy ? s.busy : s.login}</button>
        </form>
      </>
    );
  else
    content = (
      <>
        <div className="workspace-toolbar">
          <p>
            {profile.name} · {profile.role}
          </p>
          <label>
            {s.organization}
            <select
              aria-label={s.organization}
              value={profile.organization_id}
              disabled={busy || profile.must_change_password}
              onChange={(e) => {
                const id = e.target.value;
                void perform(async () => {
                  await request("/organizations/select", "POST", {
                    organization_id: id,
                  });
                  setSearch("");
                  setOffset(0);
                  setWorkClient(undefined);
                  await loadProfile();
                });
              }}
            >
              {profile.organizations.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            disabled={busy}
            onClick={() =>
              void perform(async () => {
                await request("/auth/logout", "POST");
                setProfile(null);
                setOneTime("");
              })
            }
          >
            {s.logout}
          </button>
        </div>
        {profile.must_change_password ? (
          <>
            <p role="alert">{s.passwordRequired}</p>
            {passwordForm}
          </>
        ) : (
          <>
            <nav className="workspace-tabs" aria-label={s.title}>
              <button onClick={() => setTab("clients")}>{s.clients}</button>
              {profile.role !== "tecnico" && (
                <button onClick={() => setTab("team")}>{s.team}</button>
              )}
              <button onClick={() => setTab("settings")}>{s.settings}</button>
              <button disabled={busy} onClick={() => setTab("work")}>
                {workStrings.title}
              </button>
            </nav>
            {tab === "clients" && (
              <>
                <div className="workspace-toolbar">
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      setOffset(0);
                      void perform(() => loadClients(search, 0));
                    }}
                  >
                    <label>
                      {s.search}
                      <input
                        value={search}
                        maxLength={160}
                        onChange={(e) => setSearch(e.target.value)}
                      />
                    </label>
                    <button disabled={busy}>{s.search}</button>
                  </form>
                  <button
                    disabled={busy}
                    onClick={() => {
                      setEditor("new");
                      setSelected(null);
                    }}
                  >
                    {s.newClient}
                  </button>
                </div>
                <p>
                  {s.total}: {total} {s.clientCount}
                </p>
                <div className="workspace-list">
                  {clients.map((client) => (
                    <article key={client.id}>
                      <h3>{client.name}</h3>
                      <p>
                        {client.nickname} ·{" "}
                        {client.situation === "ativo" ? s.active : s.inactive}
                      </p>
                      <button
                        onClick={() => {
                          setSelected(client);
                          setEditor(null);
                        }}
                      >
                        {s.details}
                      </button>
                      <button
                        onClick={() => {
                          setEditor(client);
                          setSelected(null);
                        }}
                      >
                        {s.editClient}
                      </button>
                    </article>
                  ))}
                </div>
                {!clients.length && <p>{s.empty}</p>}
                <div className="workspace-toolbar">
                  <button
                    disabled={busy || !offset}
                    onClick={() => {
                      const page = Math.max(0, offset - 10);
                      setOffset(page);
                      void perform(() => loadClients(search, page));
                    }}
                  >
                    {s.previous}
                  </button>
                  <button
                    disabled={busy || offset + 10 >= total}
                    onClick={() => {
                      const page = offset + 10;
                      setOffset(page);
                      void perform(() => loadClients(search, page));
                    }}
                  >
                    {s.next}
                  </button>
                </div>
                {selected && (
                  <article className="workspace-detail">
                    <h3>{selected.name}</h3>
                    <p>{selected.nickname}</p>
                    <p>
                      {selected.phone} {selected.email}
                    </p>
                    <p>{selected.notes}</p>
                    <p>
                      {s.created}: {date(selected.criado_em)}
                    </p>
                    {selected.external_refs.map((ref, index) => (
                      <p key={index}>
                        {ref.provider}: {ref.identifier} {ref.label}
                      </p>
                    ))}
                    <p>{s.history}</p>
                    <button
                      onClick={() => {
                        setWorkClient(selected.id);
                        setTab("work");
                      }}
                    >
                      {workStrings.history}
                    </button>
                  </article>
                )}
                {editor && (
                  <form
                    key={editor === "new" ? "new" : editor.id}
                    className="workspace-form"
                    onSubmit={(e) => {
                      e.preventDefault();
                      const data = new FormData(e.currentTarget);
                      void perform(async () => {
                        const ref = {
                          provider: formValue(data, "provider"),
                          identifier: formValue(data, "identifier"),
                          label: formValue(data, "label"),
                        };
                        const remaining =
                          editor === "new" ? [] : editor.external_refs.slice(1);
                        const value = {
                          name: formValue(data, "name"),
                          nickname: formValue(data, "nickname"),
                          phone: formValue(data, "phone"),
                          email: formValue(data, "email"),
                          notes: formValue(data, "notes"),
                          situation: formValue(data, "situation"),
                          external_refs:
                            ref.provider || ref.identifier
                              ? [ref, ...remaining]
                              : remaining,
                        };
                        await request(
                          editor === "new"
                            ? "/clients"
                            : `/clients/${editor.id}`,
                          editor === "new" ? "POST" : "PATCH",
                          value,
                        );
                        setEditor(null);
                        await loadClients();
                        setMessage(s.saved);
                      });
                    }}
                  >
                    <h3>{editor === "new" ? s.newClient : s.editClient}</h3>
                    <Field
                      label={s.name}
                      name="name"
                      value={editor === "new" ? "" : editor.name}
                    />
                    <Field
                      label={s.nickname}
                      name="nickname"
                      required={false}
                      value={editor === "new" ? "" : editor.nickname}
                    />
                    <Field
                      label={s.phone}
                      name="phone"
                      required={false}
                      maxLength={40}
                      value={editor === "new" ? "" : editor.phone}
                    />
                    <Field
                      label={s.email}
                      name="email"
                      type="email"
                      required={false}
                      maxLength={254}
                      value={editor === "new" ? "" : editor.email}
                    />
                    <label>
                      {s.notes}
                      <textarea
                        name="notes"
                        maxLength={4000}
                        defaultValue={editor === "new" ? "" : editor.notes}
                      />
                    </label>
                    <Situation
                      value={editor === "new" ? "ativo" : editor.situation}
                    />
                    <fieldset>
                      <legend>{s.external}</legend>
                      <Field
                        label={s.provider}
                        name="provider"
                        maxLength={80}
                        required={false}
                        value={
                          editor === "new"
                            ? ""
                            : editor.external_refs[0]?.provider
                        }
                      />
                      <Field
                        label={s.identifier}
                        name="identifier"
                        maxLength={200}
                        required={false}
                        value={
                          editor === "new"
                            ? ""
                            : editor.external_refs[0]?.identifier
                        }
                      />
                      <Field
                        label={s.label}
                        name="label"
                        required={false}
                        value={
                          editor === "new" ? "" : editor.external_refs[0]?.label
                        }
                      />
                    </fieldset>
                    <button disabled={busy}>{s.save}</button>
                    <button type="button" onClick={() => setEditor(null)}>
                      {s.cancel}
                    </button>
                  </form>
                )}
              </>
            )}
            {tab === "team" && (
              <>
                <h3>{s.team}</h3>
                <div className="workspace-list">
                  {members.map((member) => (
                    <article key={member.id}>
                      <h4>{member.name}</h4>
                      <p>{member.email}</p>
                      {profile.role === "administrador" ? (
                        <form
                          className="workspace-form"
                          onSubmit={(e) => {
                            e.preventDefault();
                            const data = new FormData(e.currentTarget);
                            void perform(async () => {
                              await request(
                                `/memberships/${member.id}`,
                                "PATCH",
                                {
                                  role: formValue(data, "role"),
                                  situation: formValue(data, "situation"),
                                },
                              );
                              await loadTeam();
                              setMessage(s.saved);
                            });
                          }}
                        >
                          <Roles value={member.role} />
                          <Situation value={member.situation} />
                          <button disabled={busy}>{s.save}</button>
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() =>
                              void perform(async () => {
                                const result = await request<{
                                  temporary_password: string;
                                }>(
                                  `/memberships/${member.id}/reset-password`,
                                  "POST",
                                );
                                setOneTime(result.temporary_password);
                                setCopied(false);
                              })
                            }
                          >
                            {s.resetPassword}
                          </button>
                        </form>
                      ) : (
                        <p>
                          {member.role} ·{" "}
                          {member.situation === "ativo" ? s.active : s.inactive}
                        </p>
                      )}
                    </article>
                  ))}
                </div>
                {profile.role === "administrador" && (
                  <>
                    <form
                      className="workspace-form"
                      onSubmit={(e) => {
                        e.preventDefault();
                        const data = new FormData(e.currentTarget);
                        void perform(async () => {
                          const result = await request<{
                            invitation_path: string;
                          }>("/invitations", "POST", {
                            email: formValue(data, "email"),
                            role: formValue(data, "role"),
                          });
                          setOneTime(location.origin + result.invitation_path);
                          setCopied(false);
                          await loadTeam();
                        });
                      }}
                    >
                      <h3>{s.invite}</h3>
                      <Field
                        label={s.email}
                        name="email"
                        type="email"
                        maxLength={254}
                      />
                      <Roles />
                      <button disabled={busy}>{s.invite}</button>
                    </form>
                    <form
                      className="workspace-form"
                      onSubmit={(e) => {
                        e.preventDefault();
                        const data = new FormData(e.currentTarget);
                        void perform(async () => {
                          const result = await request<{
                            temporary_password: string;
                          }>("/memberships", "POST", {
                            email: formValue(data, "email"),
                            name: formValue(data, "name"),
                            role: formValue(data, "role"),
                          });
                          setOneTime(result.temporary_password);
                          setCopied(false);
                          await loadTeam();
                        });
                      }}
                    >
                      <h3>{s.createTemporary}</h3>
                      <Field label={s.name} name="name" />
                      <Field
                        label={s.email}
                        name="email"
                        type="email"
                        maxLength={254}
                      />
                      <Roles />
                      <button disabled={busy}>{s.createTemporary}</button>
                    </form>
                    <h3>{s.invitations}</h3>
                    {invitations.map((item) => (
                      <p key={item.id}>
                        {item.email} ·{" "}
                        {item.usado_em
                          ? s.used
                          : `${s.pending} ${date(item.expira_em)}`}
                      </p>
                    ))}
                  </>
                )}
                <h3>{s.audit}</h3>
                {audit.map((item) => (
                  <p key={item.id}>
                    {date(item.ocorrido_em)} · {item.action}
                  </p>
                ))}
              </>
            )}
            <WorkArea
              key={profile.id + ":" + profile.organization_id}
              userId={profile.id}
              role={profile.role}
              timezone={organization?.timezone || "America/Sao_Paulo"}
              initialClient={workClient}
              hidden={tab !== "work"}
            />
            {tab === "settings" && (
              <>
                {profile.role === "administrador" && organization && (
                  <form
                    key={organization.id}
                    className="workspace-form"
                    onSubmit={(e) => {
                      e.preventDefault();
                      const data = new FormData(e.currentTarget);
                      void perform(async () => {
                        await request("/organizations/current", "PATCH", {
                          name: formValue(data, "name"),
                          timezone: formValue(data, "timezone"),
                          settings: organization.settings,
                        });
                        await loadProfile();
                        setMessage(s.saved);
                      });
                    }}
                  >
                    <h3>{s.settings}</h3>
                    <Field
                      label={s.name}
                      name="name"
                      value={organization.name}
                    />
                    <Field
                      label={s.timezone}
                      name="timezone"
                      value={organization.timezone}
                      maxLength={80}
                    />
                    <button disabled={busy}>{s.save}</button>
                  </form>
                )}
                {passwordForm}
                <button
                  disabled={busy}
                  onClick={() =>
                    void perform(async () => {
                      await request("/auth/logout-all", "POST");
                      setProfile(null);
                      setOneTime("");
                    })
                  }
                >
                  {s.logoutAll}
                </button>
              </>
            )}
          </>
        )}
      </>
    );
  return (
    <section className="workspace" id="organizacao" aria-label={s.title}>
      <h2>{s.title}</h2>
      {error && (
        <p role="alert" className="error">
          ! {error}
        </p>
      )}
      {message && <p role="status">{message}</p>}
      {content}
      {oneTime && profile && (
        <aside className="workspace-secret">
          <p>{s.temporaryNotice}</p>
          <output>{oneTime}</output>
          <button
            onClick={() =>
              void perform(async () => {
                await navigator.clipboard.writeText(oneTime);
                setCopied(true);
              })
            }
          >
            {copied ? s.copied : s.copy}
          </button>
          <button onClick={() => setOneTime("")}>{s.cancel}</button>
        </aside>
      )}
      <p>
        <a href="https://github.com/matheusenalt/SolDesk">{s.source}</a>
      </p>
    </section>
  );
}
