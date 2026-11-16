# Decisões

## Adotadas na fase 01

- Monorepo novo, sem copiar código ou dados de outros projetos.
- Python 3.13, FastAPI/Pydantic, SQLAlchemy 2, Alembic; PostgreSQL 17.
- React 19, TypeScript estável instalado, Vite e Tailwind v4.
- Dependências exatas registradas nos lockfiles após validação local.
- TypeScript 6.0.3 mantido: 7.0.2 não é compatível com o peer de typescript-eslint
  8.72.2. Sem forçar a resolução. Vitest 5.1.0 e ESLint 10.15.0 validados.
- Override minimatch `^11.0.1` limitado ao typescript-estree corrige advisory
  GHSA-g3hv-75wg-m249; lint, testes e build foram executados depois.
- Banco SQLite apenas para testes rápidos; Compose é a referência PostgreSQL.
- Identidade da instalação em migração inicial singleton, independente de hostname.
- Modo community padrão. `ALLOW_ORG_SIGNUP=false` reservado, sem cadastro nesta fase.
- Fase 02 deverá separar papel runtime do papel de migração para RLS efetivo.
- Tokens oficiais preservados; extensões limitadas a zinc e feedback acessível.

## Em aberto

Nome/identidade definitivos, escopo do MVP,
comparação/benchmark de transcrição, prazos de revisão, hospedagem Community/Cloud
e integrações prioritárias.
Finalizações: somente autor revisa, conforme requisitos. Artigos: proposta de
gestor/admin publicar, sem autopublicação por padrão, ainda a confirmar quando
a funcionalidade for implementada. Prazos rígidos de revisão continuam em aberto.

## Licenciamento aprovado pelo titular

- GNU AGPL versão 3 somente, identificador `AGPL-3.0-only`, escolhida explicitamente
  pelo titular para o código próprio. Não foi concedida a opção de versões futuras.
- Texto oficial baixado de `https://www.gnu.org/licenses/agpl-3.0.txt`, sem edição.
- Instalações próprias, contribuições e hospedagem comercial seguem a mesma
  licença. Não foi estabelecida licença comercial alternativa.
- A autorização atual permite o primeiro commit e push da fase 01 com as
  pendências de infraestrutura documentadas. O prompt 02 só começa após o aceite
  obrigatório da fase 01; essa condição substitui a autorização anterior de avanço.
- Inventário e condições de terceiros em [LICENCAS.md](LICENCAS.md).

## Adotadas na fase 02

- PostgreSQL obrigatório para operações autenticadas; SQLite preservado apenas
  para o aceite rápido das rotas de instalação da fase 01.
- Conta runtime separada e RLS com FORCE; contexto transacional e repositório
  único. Migração aditiva, sem exclusão de volumes ou dados existentes.
- Sessões opacas em cookies HttpOnly/Secure em produção/SameSite Strict;
  CSRF com grant persistente vinculado à sessão. Sem JWT/localStorage na web.
- Argon2id via argon2-cffi; dependências e licenças incluídas nos inventários.
- Rate limit persistente por IP/conta e bloqueio progressivo sem Redis nesta fase.
- Community: só bootstrap explícito de uma empresa. Cloud: cadastro público
  somente com ALLOW_ORG_SIGNUP, padrão desligado. Seed de duas empresas só em
  Cloud não produtivo; idempotente e sem redefinir credenciais existentes.
- Identidades compartilhadas não têm senha global redefinida por admin de uma
  só empresa. Convites para contas existentes exigem a senha atual do titular.
- Todos os membros ativos acessam todos os clientes da sua organização;
  somente admin administra equipe/configurações. Gestor consulta equipe/auditoria.
- Busca ignorando acentos/caixa com unaccent e pg_trgm; nomes únicos por empresa,
  apelidos não únicos, paginação offset estável por criação/UUID.
- Mobile terá fluxo próprio na fase 06; nenhuma credencial mobile fictícia.

## Adotadas na fase 03

- Finalizações são conferidas e confirmadas exclusivamente pelo autor, em tela
  ou lote atômico. Não existe aprovação do gestor nem confirmação automática.
- Pendência acima de 24 h recebe destaque visual; não é SLA obrigatório, ranking
  ou avaliação do técnico. Só confirmados contam no histórico oficial.
- Entrada exclusivamente textual e humana. Chamados abrem diretamente, inclusive
  urgentes; conhecimento é somente rascunho, com publicação reservada à fase 05.
- Conteúdo original/recebimento imutáveis; texto humano editado/versionado antes
  de confirmar. Horários distintos, UTC no banco e IANA na interface. Hora local
  ambígua/inexistente exige offset explícito, sem escolher silenciosamente.
- Um registro tem um destino; Derivar cria outro rascunho com origem e mesmo
  horário do fato. Não transforma nem apaga o original.
- Idempotência opcional para criação/derivação, obrigatória no fluxo da UI;
  escopo por organização/usuário/operação, chave em hash e lock transacional.
- Técnico vê chamados próprios, atribuídos ou em que participa; gestão vê a fila
  da empresa. Responsável/gestão opera, solicitante/gestão encerra. Resolver e
  encerrar são ações separadas; reabertura mantém o ticket e o histórico.
- Notificações internas por destinatário, polling de 15 s; sem serviço externo.
- Sem novas tecnologias/dependências; AGPL e inventários anteriores preservados.

## Referências técnicas

- https://fastapi.tiangolo.com/tutorial/testing/
- https://alembic.sqlalchemy.org/en/latest/tutorial.html
- https://docs.sqlalchemy.org/en/20/
- https://vite.dev/guide/
- https://tailwindcss.com/docs/installation/using-vite
- https://docs.docker.com/compose/how-tos/startup-order/
- https://docs.docker.com/desktop/setup/install/windows-install/

As fontes consultadas e versões efetivamente instaladas constam no relatório de validação.
