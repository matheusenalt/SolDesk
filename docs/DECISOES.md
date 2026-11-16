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
a funcionalidade for implementada. Não há implementação de revisões nesta fase.

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

## Referências técnicas

- https://fastapi.tiangolo.com/tutorial/testing/
- https://alembic.sqlalchemy.org/en/latest/tutorial.html
- https://docs.sqlalchemy.org/en/20/
- https://vite.dev/guide/
- https://tailwindcss.com/docs/installation/using-vite
- https://docs.docker.com/compose/how-tos/startup-order/
- https://docs.docker.com/desktop/setup/install/windows-install/

As fontes consultadas e versões efetivamente instaladas constam no relatório de validação.
