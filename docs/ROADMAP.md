# Roadmap

1. Protótipo local: arquitetura, tokens, saúde, identidade persistente e setup.
2. Operação básica: organizações, autenticação, RLS, clientes e equipe.
3. Registros, chamados, tempos, revisões e notificações.
4. Áudio funcional: fila Redis, worker, revisão humana e storage.
5. Produto ampliado: conhecimento, busca PostgreSQL e relatórios descritivos.
6. Aplicativo mobile: Expo, QR seguro e conexão explícita ao servidor.
7. Conectores mock, ponta a ponta e revisão de segurança/privacidade.

Evoluções: restrição de acesso por cliente, SMTP opcional, busca semântica,
push remoto, políticas de retenção e operação Cloud. Prioridades do MVP em aberto.
Cada fase exige validação e documentação próprias antes da próxima.

Licenciamento do código próprio: GNU AGPL v3 somente, aprovado pelo titular;
instalações próprias, contribuições e eventual hospedagem comercial seguem a
licença. A publicação inicial não encerra o aceite de infraestrutura da fase 01.
O aceite Compose/PostgreSQL da fase 01 foi executado em Windows/WSL 2, incluindo
testes de navegador contra os contêineres.

Fase 02: organizações, autenticação, equipe, clientes e RLS implementados e
validados localmente com PostgreSQL e E2E. Restrição por cliente é evolução futura; atualmente
todos os membros ativos veem todos os clientes da organização. Registros,
chamados, relatórios operacionais e arquivos continuam nas próximas fases.
