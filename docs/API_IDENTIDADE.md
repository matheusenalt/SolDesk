# API de identidade, organizações e clientes

Contrato executável em `/docs` e `/openapi.json`. Erros usam
`application/problem+json`; os detalhes de SQL, parâmetros e exceções não são
retornados. Os corpos de entrada rejeitam campos extras.

## Sessão web

1. `GET /api/v1/auth/csrf` emite um cookie HttpOnly e retorna `csrf_token` no JSON.
2. Todos os POST/PATCH exigem `X-CSRF-Token` igual ao cookie e ao hash de um
   registro não expirado no servidor, vinculado à sessão corrente quando existir.
   Origin, quando presente, precisa estar na lista explícita `CORS_ORIGINS`.
   Login, cadastro público e aceite de convite também exigem CSRF.
3. `POST /api/v1/auth/login`: `{email,password}`. Emite sessão opaca aleatória em
   cookie HttpOnly/SameSite=Strict; Secure em produção. Só o SHA-256 da credencial
   fica no banco. Nenhum token é salvo no localStorage.
4. `GET /api/v1/me` retorna identidade, papel, organização corrente, vínculos ativos
   e `must_change_password`. Sessões duram 12 h por padrão (`SESSION_HOURS`).
5. `POST /api/v1/auth/logout` e `/auth/logout-all` revogam sessão atual ou todas
   as sessões do usuário. `POST /auth/password` recebe `current_password` e
   `new_password`, revoga sessões antigas e emite uma nova.

Senha de 12–128 caracteres, hash Argon2id (64 MiB, 3 iterações, paralelismo 4,
parâmetros padrão da versão instalada). Espaços da senha são preservados.
Credenciais inválidas, conta inexistente e ausência de vínculo retornam mensagem
genérica de login. Rate limit persistente por IP e conta, com locks transacionais:
30 tentativas/IP e 5/conta em um minuto; a partir de 5 falhas ocorre bloqueio
progressivo de 30 s até 15 min. O IP vem da conexão ao servidor, não de um header
forjado. Atrás de Nginx, o IP visto pela API pode ser o proxy: o limite por IP é
conservador/compartilhado e o limite por conta permanece independente. Confiar em
cadeias de proxy externas exige configuração própria antes de produção.

`GET /auth/config` informa apenas se o cadastro público está disponível.
Sessões bearer legadas usam [acesso curto e refresh rotativo](API_SESSAO_TOKEN.md),
separados do cookie/CSRF web. O cliente nativo foi descontinuado.

## Organizações e integrantes

- `GET /organizations`: somente vínculos ativos da identidade autenticada.
- `POST /organizations/select`: `{organization_id}` como seleção; vínculo é
  verificado no servidor antes de persistir o novo contexto na sessão.
- `PATCH /organizations/current`: `{name,timezone,settings}`; somente administrador.
  Fuso IANA validado; padrão `America/Sao_Paulo`. `settings` aceita até 20 flags
  booleanas, sem campo para armazenar segredos.
- `POST /organizations`: `{name,email,password,organization_name,slug,timezone}`.
  Só Cloud e `ALLOW_ORG_SIGNUP=true`; desligado por padrão. Community usa apenas
  bootstrap explícito e não disponibiliza cadastro público de empresas.
- `GET /memberships`; `POST /memberships`: `{name,email,role}` gera senha temporária
  aleatória, retornada uma vez e com troca obrigatória. Conta já existente exige convite.
- `PATCH /memberships/{id}` recebe ambos `role` e `situation`. Papéis:
  `administrador`, `gestor`, `tecnico`; situações: `ativo`, `inativo`.
- `POST /memberships/{id}/reset-password`: senha temporária, troca obrigatória e
  revogação de sessões; consulte a proteção de identidades compartilhadas em
  [PERMISSOES.md](PERMISSOES.md).
- `GET/POST /invitations`: criação `{email,role}`; validade de dois dias.
  O link retornado usa fragmento `/#convite=...`, não query enviada em URLs/logs.
- `POST /invitations/accept`: `{email,name,password,token}`. Uso único protegido
  por lock de linha. Identidade existente deve confirmar sua senha atual antes
  de receber o vínculo; um convite não redefine sua senha nem assume a conta.

## Clientes

`GET/POST /clients`, `GET/PATCH /clients/{id}`. Atualização PATCH nesta versão
recebe o cadastro completo, preservando campos opcionais enviados pela interface.
Campos: `name`, `nickname`, `phone`, `email`, `notes`, `situation`, `external_refs`.
Referências: `{provider,identifier,label}`; até 20, substituídas em conjunto.
São apenas metadados; não há integração externa ou envio de mensagens.

Busca `search` por nome/apelido usa `unaccent`/caixa e índices GIN `pg_trgm`.
`%` e `_` digitados são tratados como texto. Paginação offset documentada:
`offset=0`, `limit=20`, máximo 100, ordenação estável por criação UTC e UUID.
Resposta `{items,total,offset,limit}`. Alterações simultâneas podem mudar páginas;
não é snapshot de relatório. Não se envia organization_id em cadastros.

Nome obrigatório 2–160, apelido até 160, telefone até 40, e-mail opcional validado,
observações até 4.000 caracteres. Espaços externos são removidos. Nome duplicado
na mesma organização, ignorando acentos e caixa, retorna 409 (também inativos).
Apelidos podem repetir. Outra organização pode usar o mesmo nome. Não se exige
documento fiscal e não se deduz cadastro a partir de integrações.

## Isolamento e auditoria

`Context.query/get` injeta o tenant do servidor. Toda transação define contexto
com `set_config(..., true)`, equivalente transacional a SET LOCAL, e perde o
contexto ao terminar, inclusive no pool. Clientes, referências, convites,
integrantes, organização e auditoria têm políticas RLS; identidades, sessões,
CSRF e throttles são tabelas internas de autenticação global, sem CRUD público.
As linhas pertinentes têm `organization_id` NOT NULL e índice. Referências
externas possuem FK composta impedindo vínculo com cliente de outra organização.

A API usa `soldesk_runtime`, sem superusuário/BYPASSRLS/propriedade das tabelas;
as rotas de negócio recusam credenciais de migrador. Migração/CLI usam conexão
separada. Duas funções SECURITY DEFINER com search_path fixo têm execução
restrita: localizar a organização de um token de convite válido e contar os
vínculos globais antes de redefinir senha. Nenhuma recebe SQL ou retorna segredos.

Auditoria (`GET /audit-events`, gestão/admin) registra ator, organização, ação,
entidade, antes/depois relevantes, horário UTC e origem. A API só recebe SELECT
e INSERT nessa tabela. Senhas, hashes e tokens são excluídos por construção.
Logs estruturados não incluem corpo/query; access log do Nginx fica desligado.

## Fontes primárias

- [PostgreSQL RLS](https://www.postgresql.org/docs/17/ddl-rowsecurity.html).
- [OWASP CSRF](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).
- [Argon2-cffi](https://argon2-cffi.readthedocs.io/en/stable/howto.html).
