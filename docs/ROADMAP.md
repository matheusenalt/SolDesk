# Roadmap

1. Protótipo local: arquitetura, tokens, saúde, identidade persistente e setup.
2. Operação básica: organizações, autenticação, RLS, clientes e equipe.
3. Registros, chamados, tempos, revisões e notificações.
4. Áudio funcional: fila Redis, worker, revisão humana e storage.
5. Produto ampliado: conhecimento, busca PostgreSQL e relatórios descritivos.
6. Aplicativo mobile: Expo, QR seguro e conexão explícita ao servidor.
7. Conectores mock, ponta a ponta e revisão de segurança/privacidade.

Evoluções: restrição de acesso por cliente, SMTP opcional, busca semântica,
push remoto e operação Cloud de produção. Prioridades do MVP em aberto.
Cada fase exige validação e documentação próprias antes da próxima.

Licenciamento do código próprio: GNU AGPL v3 somente, aprovado pelo titular;
instalações próprias, contribuições e eventual hospedagem comercial seguem a
licença. A publicação inicial não encerra o aceite de infraestrutura da fase 01.
O aceite Compose/PostgreSQL da fase 01 foi executado em Windows/WSL 2, incluindo
testes de navegador contra os contêineres.

Fase 02: organizações, autenticação, equipe, clientes e RLS implementados e
validados localmente com PostgreSQL e E2E. Restrição por cliente é evolução futura; atualmente
todos os membros ativos veem todos os clientes da organização.

Fase 03: registros textuais, revisão própria/lote, histórico confirmado,
chamados com conversa/menção/intervalos de espera, notificações internas,
concorrência, idempotência e derivação implementados. Evidências e limites em
[VALIDACAO_PROMPT_03](VALIDACAO_PROMPT_03.md). Sem novas dependências.

Fase 04: áudio assíncrono, Redis/RQ, worker/dispatcher, armazenamento local/S3
privado, anexos de cliente/chamado, links temporários, revisão humana, glossário,
templates versionados, retenção auditada e ditado progressivo implementados.
Mock é o padrão offline e não reconhece fala. faster-whisper é integração opcional;
benchmark com modelo real permanece pendente, explicitamente previsto no prompt.
Evidências: [VALIDACAO_PROMPT_04](VALIDACAO_PROMPT_04.md).
Fase 05: conhecimento estruturado/revisado/versionado, busca PostgreSQL com códigos
e acentos, contexto de cliente, sugestões e consultas agregadas implementados.
Relatórios descritivos, eventos por ator, calendário/fuso, mediana/P90/pausas,
equipes e CSV auditado com escopo próprio de técnico. Aceite local aprovado:
65 pytest, 32 cenários autenticados e 4 regressões de instalação, lint/build/Docker;
[métricas](METRICAS.md) e [validação](VALIDACAO_PROMPT_05.md).
Publicada em main (`160297a`); [Actions aprovado](https://github.com/matheusenalt/SolDesk/actions/runs/43928535399),
65 pytest PostgreSQL e 32 E2E Chromium Ubuntu em execução completa.
Parar após validar/documentar/publicar a Fase 05; não iniciar Prompt 06.
