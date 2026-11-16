# SOLDesk — PROMPT 02/06
## Empresas, usuários, clientes e controle de acesso

### PROMPT PARA O DESENVOLVEDOR

Continue **no mesmo repositório SolDesk** do Prompt 01. Primeiro leia `AGENTS.md`, `docs/REGRAS_DO_PROJETO.md`, `ARQUITETURA.md`, `STATUS.md` e os arquivos reais. Não recrie o projeto, não substitua trabalho concluído e preserve alterações existentes.

**Contexto:** SolDesk tem painel web e app mobile futuro. O núcleo é independente de Nextcloud/GLPI. A instalação **Cloud** poderá hospedar várias empresas; a **Community** é uma empresa em servidor próprio. Por isso o isolamento de dados existe desde o começo, mesmo que a Community use uma só organização.

#### Entregas obrigatórias

1. **Organizações:** `Organization` (UUID, nome, slug, **fuso horário (IANA, padrão `America/Sao_Paulo`)**, configurações, criação), `User` e `OrganizationMembership` (usuário, organização, papel, situação). Um usuário pode pertencer a mais de uma organização sem cruzamento de dados. A coluna de isolamento chama-se **`organization_id`** em todas as tabelas de negócio (padrão para todas as fases).
2. **Modos de instalação:** respeitar `SOLDESK_MODE`. Em `community`, uma única organização (criada no bootstrap) e cadastro público de novas empresas desligado. Em `cloud`, o cadastro no site cria uma empresa e seu primeiro administrador, controlado pela flag `ALLOW_ORG_SIGNUP` (desligada por padrão) e com rate limit. Registrar a escolha em `docs/DECISOES.md`.
3. **Papéis e permissões:** administrador, gestor e técnico, com **matriz explícita em `docs/PERMISSOES.md`** (recurso × ação × papel). Administrador gerencia integrantes e configurações; gestor acompanha a equipe e relatórios; técnico opera registros e seus chamados. Definir e documentar o padrão de visibilidade de clientes: **todos os membros da organização veem todos os clientes dela** (restrição por cliente fica como evolução futura, registrada no ROADMAP). Proteções: não é possível remover ou rebaixar o **último administrador**; ninguém altera o próprio papel para um superior.
4. **Login seguro:** hash Argon2id, validação de senha, rate limit por IP e por conta, bloqueio temporário progressivo, mensagens que não revelam se o e-mail existe, logout e expiração/revogação de sessão (incluindo "sair de todos os dispositivos" e revogação ao remover membro). Web: cookies HttpOnly/Secure(em produção)/SameSite **com proteção CSRF** para métodos que alteram estado. Mobile (Prompt 06): token de acesso curto + refresh com rotação, entregue por fluxo próprio que permita armazenamento seguro. **Nunca guardar token longo em localStorage.**
5. **Bootstrap, convites e senhas (sem depender de e-mail/SMTP):**
   - Comando/fluxo explícito cria a primeira organização fictícia e o primeiro administrador; a senha inicial é informada por quem executa ou gerada e exibida uma única vez, nunca fixa no código.
   - Administrador adiciona funcionários por **convite com token de uso único e expiração** (link copiável) ou criando o usuário com senha temporária que **exige troca no primeiro login**. Ninguém entra numa empresa só por conhecer slug/ID.
   - Redefinição de senha nesta fase: feita por administrador (gera senha temporária/link único). Envio por e-mail fica como opcional futuro (SMTP configurável), sem ser exigido.
6. **Clientes:** cadastro por organização com nome, apelido, contatos opcionais (telefone, e-mail), observações e situação ativo/inativo; **referências externas opcionais** (`ClientExternalRef`: provedor, identificador, rótulo — ex.: grupo de WhatsApp, ID em outro helpdesk), apenas armazenadas, sem integração real. Busca por nome **e apelido**, paginação por cursor ou offset documentado, validação e política de duplicidade documentada. **A busca ignora acentos e caixa** ("mercearia" encontra "Merceária Ramos"); usar `unaccent` + `pg_trgm` no PostgreSQL, com índices.
7. **Frontend:** login, alternância de organização quando aplicável, equipe/usuários (convites, papéis, desativar), lista/pesquisa/cadastro/edição de clientes. Responsivo para celular. Reutilizar a paleta e os tokens de `docs/IDENTIDADE_SOL.md`, sem escolher cores novas por tela; estados (ativo/inativo, erro) com ícone + texto.
8. **Dados e isolamento:** PostgreSQL + Alembic; `organization_id` obrigatório (NOT NULL, com índice) nas entidades pertinentes. O filtro vem do contexto autenticado, **via camada única de acesso a dados** (dependência/repositório que injeta o tenant) para evitar esquecer o filtro em alguma consulta. **Implementar Row-Level Security como reforço (defesa em profundidade)** e documentar a escolha em `DECISOES.md`, atentando aos pontos que costumam falhar: a API deve conectar com um papel de banco **que não seja superusuário nem dono das tabelas** (ou usar `FORCE ROW LEVEL SECURITY`), o tenant é definido por transação (`SET LOCAL`) e testado com o pool de conexões, e as migrações rodam com papel separado. Incluir teste que prova que, sem o filtro da aplicação, o RLS ainda bloqueia a leitura cruzada.
9. **Auditoria mínima e reutilizável:** tabela genérica de auditoria (ator, organização, ação, entidade, antes/depois relevantes, data, IP/origem) para alteração de papéis, convites, desativações, redefinição de senha e demais ações administrativas, **sem senhas, tokens ou segredos** nos registros e nos logs. As fases seguintes reutilizam essa infraestrutura.
10. **Consulta do cliente:** tela do cliente com dados cadastrais e espaço reservado para histórico e arquivos (preenchidos nas próximas fases), sem tela falsa de sucesso.

#### API indicativa

- `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `GET /api/v1/me`
- `GET/POST /api/v1/organizations`; convites e membros (`/memberships`, `/invitations`)
- `GET/POST/PATCH /api/v1/clients`; `GET /api/v1/clients?search=...`

Adapte às boas práticas e documente qualquer mudança no OpenAPI e em `docs/`.

#### Testes obrigatórios

- Usuário da empresa A não lista, consulta, modifica nem adivinha IDs de clientes da empresa B (teste HTTP, inclusive acesso direto por UUID, e teste do RLS isolado do filtro da aplicação).
- Técnico não promove a si mesmo a administrador; não é possível remover/rebaixar o último administrador.
- Usuário removido da empresa perde acesso imediato (sessões revogadas).
- Convite expirado ou já usado é recusado; senha temporária força troca; rate limit de login funciona; CSRF bloqueia requisição sem token.
- Busca por apelido, com e sem acento, e paginação funcionam; regras de validação e duplicidade documentadas.
- Logs e auditoria não contêm senha/token (teste que procura padrões).
- A interface usa dados reais da API; nenhuma tela de sucesso falsa.

#### Critério de entrega

Subir via Docker Compose usando o setup do Prompt 01 (agora com `scripts/seed-demo` criando **duas empresas fictícias, um administrador e um técnico por empresa e clientes diferentes**, de forma idempotente). Mostrar resultado dos testes automatizados e um roteiro manual no navegador (PowerShell e bash quando diferirem). Atualizar `ARQUITETURA.md`, `TESTE_LOCAL.md`, `STATUS.md`, `PERMISSOES.md` e a documentação da API. **Não avance para o Prompt 03 sem confirmação.**
