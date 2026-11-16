# Estado do SolDesk

Atualizado em 16/11/2026. SolDesk Web responsivo; Android/iOS nativos descontinuados.
**Não homologado para produção. Somente dados fictícios.**

## Funciona agora — confirmado por código e testes locais

- Organizações, membros/convites, autenticação web/CSRF, papéis, clientes e isolamento
  PostgreSQL RLS. Sessão legada por token e refresh antirreplay preservados na API.
- Registros textuais, confirmação pelo autor, versões e histórico; chamados com
  responsável/prioridade, comentários, menções, esperas, resolução/encerramento/reabertura.
- Áudio/anexos privados, gravação web com prévia e fallback textual; processamento
  assíncrono Redis/RQ, prioridade, lease/retry/idempotência, templates/glossário e retenção.
- Conhecimento estruturado com revisão editorial humana, versões e busca PostgreSQL;
  relatórios factuais com fuso/filtros/equipes, CSV auditado e escopo próprio do técnico.
- Interface única, strings pt-BR centralizadas, temas e contraste; não há cliente nativo.

## Parcial ou com limitações

- Mock reutiliza texto humano; **não reconhece fala**. faster-whisper opcional existe,
  mas inferência/qualidade/desempenho reais não foram homologados.
- Finalização exige cliente; validação pelo autor segue acoplada ao ciclo do registro.
  Não existe validação humana independente por versão para qualquer leitor autorizado.
- Sistema/software é texto, não catálogo; busca é de clientes/artigos, não global.
- Chamados não possuem todo o fluxo futuro de prazo/aceite/inatividade; equipe serve
  aos relatórios. Relatórios são limitados em memória e não têm benchmark produtivo.
- Upload padrão 25 MiB, teto 64 MiB; 80 MB não suportados. Sem quotas/streaming completo.
- Restauração, HTTPS/privacidade de produção, carga e auditoria independente pendentes.
  Ver [limitações](docs/LIMITACOES.md), [segurança](docs/SEGURANCA.md), [backup](docs/BACKUP.md).

## Planejado — não implementado

Atendimento contínuo/atividade interna; validação independente; catálogo de sistemas;
tarefas e calendário; busca global/por voz/semântica; confirmação técnica por versão;
PWA; CSV/sincronização externa; Nextcloud opcional; instalador Linux completo.
Detalhes e decisões: [visão](docs/VISAO.md) e [evolução](docs/ROADMAP.md).

## Validação e publicação

Saneamento documental validado localmente em 16/11/2026, após separar instruções
operacionais de relatórios históricos e preservar contratos com nomes por domínio.
Foi retirado um comentário redundante; código executável e JavaScript gerado não mudaram.

| Verificação executada | Resultado |
|---|---|
| Backend PostgreSQL/Redis/ffmpeg isolados | PASSOU: 72 testes; 1 aviso de depreciação Starlette/httpx |
| Unitários web | PASSOU: 6 testes; também executados entre os grupos de limpeza |
| Navegador autenticado | PASSOU: 32 cenários Edge desktop/emulação móvel, sem skips |
| Instalação pública | PASSOU: 4 cenários desktop/emulação móvel |
| Ruff/ESLint, formatação, TypeScript e build | PASSOU |
| Contraste e documentação | PASSOU: 32 pares WCAG e 127 destinos locais de links |
| Preservação de escopo | PASSOU: backend, migrações, testes, dependências, licenças e infraestrutura sem alteração |

Restauração completa, inferência real, dispositivo físico e produção:
**NÃO EXECUTADO nesta validação**. Instruções documentadas não representam homologação.

Descontinuação nativa publicada em [feed935](https://github.com/matheusenalt/SolDesk/commit/feed935fb553d8346fddfa80672206bd9eabab05).
[GitHub Actions aprovado](https://github.com/matheusenalt/SolDesk/actions/runs/43979286026)
para esse commit. Migrações até `0006a` e controles de API preservados; Android
anterior não foi aprovado, foi descontinuado. Saneamento documental validado
localmente e aguardando aprovação, **sem commit/push próprio**.
