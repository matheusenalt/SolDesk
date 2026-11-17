# SolDesk

Plataforma web independente e open source de suporte técnico, com clientes,
histórico, chamados, áudio/anexos privados, conhecimento revisado e relatórios.
Uma interface React responsiva para computador e celular; Android/iOS nativos descontinuados.
Paleta e navegação em evolução; a [identidade definitiva](docs/IDENTIDADE_SOL.md)
depende do arquivo oficial da logo, ainda não localizado.

Gravação web oferece pausa quando suportada, prévia e recuperação de envio.
Há uma base de manifesto PWA, sem modo offline; ícones e instalação homologada
dependem da logo oficial. Consulte [operação de mídia](docs/OPERACAO_MIDIA.md).

A API oferece validação humana de fidelidade por versão exata, independente da
resolução de chamados. A interface dessa validação ainda está pendente; consulte
o [contrato de registros](docs/API_ATENDIMENTOS.md) e o [estado real](STATUS.md).

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

Atendimentos contínuos disponíveis na web e API: atualizações datadas, próxima ação,
retomada, transferência e finalização com mesmo ID/histórico. Atividade interna
também aceita finalização sem cliente artificial. Interface específica pendente;
contratos e limites em [API de atendimentos](docs/API_ATENDIMENTOS.md).

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

## Catálogo de sistemas

Catálogo estruturado disponível na API, com vínculos N:N por cliente, versão em
uso, instantâneos históricos e reconciliação manual do texto legado. A interface
do catálogo está pendente. Consulte o [contrato de sistemas](docs/API_SISTEMAS.md).

## Tarefas

A API oferece tarefas internas ou ligadas a clientes, sistemas, atendimentos e
chamados, com responsável/equipe, datas e histórico independente. Conclusão simples
não exige revisão editorial. A interface específica está pendente.
Consulte o [contrato de tarefas](docs/API_TAREFAS.md).
