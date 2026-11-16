# Validação do prompt 01

## Verificação para publicação em 15/11/2026

- Backend: `pytest backend/tests -q`, 5 testes aprovados com SQLite temporário.
- Ruff: lint e formatação aprovados em `backend` e `scripts/tokens.py`.
- Tokens: `scripts/tokens.py --check` aprovado, 32 pares de contraste verificados.
- Web: lint e formatação aprovados; Vitest com 3 testes aprovados; build
  TypeScript/Vite aprovado.
- Playwright com Edge: 4 testes aprovados, desktop e emulação móvel, com API real.
- As execuções Python e esbuild bloqueadas pelo sandbox foram repetidas com
  permissão ampliada; os resultados acima são das execuções concluídas.
- Busca textual por padrões comuns de chaves privadas e tokens sem ocorrências
  nos arquivos do projeto examinados; não equivale a gitleaks ou auditoria completa.
- Cache local `Microsoft/` e relatórios Playwright excluídos do versionamento.
- `origin` configurado para `https://github.com/matheusenalt/SolDesk.git`.

## Pendências

Docker não encontrado: Compose, PostgreSQL, build de imagens, reinício e
persistência do volume não foram validados. Permanece o aviso upstream do
TestClient/httpx. pip-audit e gitleaks não foram executados nesta verificação.

O titular solicitou publicar a implementação atual e, após a publicação, iniciar
o prompt 02. Em seguida escolheu GNU AGPL v3 somente e condicionou o início do
prompt 02 ao aceite obrigatório da fase 01. Texto oficial baixado sem alterações,
metadados e documentação atualizados. Revisão de 38 distribuições Python e 272
entradas npm documentada em [LICENCAS.md](LICENCAS.md).

Docker Desktop 4.99.0/Engine 29.9.3 localizado na instalação do usuário; daemon
respondeu e WSL usa versão 2. Os testes Compose serão executados após o primeiro
push, conforme a ordem solicitada. Não há aprovação de infraestrutura nesta etapa.
