# SolDesk

Plataforma web independente e open source de suporte técnico, com clientes,
histórico, chamados, áudio/anexos privados, conhecimento revisado e relatórios.
Uma interface React responsiva para computador e celular; Android/iOS nativos descontinuados.

**Estado:** núcleo web funcional e testado localmente; não homologado para produção.
Use somente dados fictícios. O mock padrão NÃO reconhece fala; transcrição real,
HTTPS, restauração e privacidade produtiva ainda exigem homologação.

## Instalar localmente

Requer Git, navegador e Docker com Compose. Windows: Docker Desktop/WSL 2;
Linux: Docker Engine e plugin Compose. Não precisa instalar Python/Node no host
para operar os contêineres.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
```

```bash
bash scripts/setup.sh
```

Abra http://localhost:8080 e http://localhost:8000/docs.
Crie o primeiro administrador explicitamente seguindo [instalação](docs/INSTALACAO.md).
Setup gera segredos locais, executa migrações e preserva volumes; não configura
produção, TLS nem backup. PostgreSQL e Redis ficam na rede interna.

## Desenvolver e testar

Stack: Python/FastAPI/Pydantic/SQLAlchemy/Alembic, PostgreSQL com RLS;
React/TypeScript/Vite/Tailwind; Redis/RQ e storage privado. Dependências nos locks.
S3, antivírus e faster-whisper são opcionais; Nextcloud não é necessário.

```text
docker compose --profile test run --build --rm tests
```

O comando usa banco/Redis isolados e dados fictícios. Lint, testes rápidos, build
e navegador: [TESTE_LOCAL.md](TESTE_LOCAL.md). Para desenvolvimento com reload:
`docker compose --profile dev up -d --build db migrate api-dev web-dev`.

## Estado e documentação

- [Funciona agora, parcial, planejado e testes executados](STATUS.md).
- [Arquitetura](ARQUITETURA.md), [visão](docs/VISAO.md) e [evolução](docs/ROADMAP.md).
- [Instalação](docs/INSTALACAO.md), [mídia](docs/OPERACAO_MIDIA.md),
  [segurança](docs/SEGURANCA.md), [backup](docs/BACKUP.md) e [limitações](docs/LIMITACOES.md).
- API: [identidade](docs/API_IDENTIDADE.md), [registros/chamados](docs/API_ATENDIMENTOS.md),
  [mídia](docs/API_MIDIA.md), [conhecimento/relatórios](docs/API_CONHECIMENTO_RELATORIOS.md)
  e [sessão legada por token](docs/API_SESSAO_TOKEN.md).
- [Permissões](docs/PERMISSOES.md), [estados](docs/ESTADOS.md), [métricas](docs/METRICAS.md),
  [decisões](docs/DECISOES.md) e [contribuição](CONTRIBUTING.md).

## Licença

Código próprio sob GNU AGPL v3 somente (`AGPL-3.0-only`), escolhida pelo titular.
Texto oficial preservado em [LICENSE](LICENSE). Instalação própria, contribuições
e hospedagem comercial seguem os termos da licença. Dependências e condições de
terceiros: [licenciamento](docs/LICENCAS.md). Nenhum dado ou código privado de empregadores.
