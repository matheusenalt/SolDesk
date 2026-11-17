# Estado do SolDesk

Atualizado em 17/11/2026. SolDesk Web responsivo; Android/iOS nativos descontinuados.
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

- Paleta provisória, ações principais e responsividade ajustadas; **identidade
  definitiva pendente da logo oficial**, não localizada. Nenhuma logo foi recriada.
  Ver [identidade e medições](docs/IDENTIDADE_SOL.md).
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
instalação PWA com ícones oficiais; CSV/sincronização externa; Nextcloud opcional; instalador Linux completo.
Detalhes e decisões: [visão](docs/VISAO.md) e [evolução](docs/ROADMAP.md).

## Validação anterior e publicação

Paleta provisória e responsividade validadas localmente em 16/11/2026. Mesmos
componentes React, sem novo frontend ou modalidades de negócio. Ações destacadas
abrem o formulário existente e pesquisam artigos publicados; não há busca global.
Identidade definitiva não concluída: depende do arquivo oficial da logo.

| Verificação executada | Resultado |
|---|---|
| Backend PostgreSQL/Redis/ffmpeg isolados | PASSOU: 72 testes; 1 aviso de depreciação Starlette/httpx |
| Unitários web | PASSOU: 6 testes; também executados entre os grupos de limpeza |
| Navegador autenticado | PASSOU: 36 cenários Edge desktop/emulação móvel, sem skips |
| Instalação pública | PASSOU: 4 cenários desktop/emulação móvel |
| Ruff/ESLint, formatação, TypeScript e build | PASSOU |
| Contraste e foco | PASSOU: 32 pares WCAG; foco sólido 3 px/afastamento 4 px, navegação Tab e contraste nos dois temas |
| Responsividade | PASSOU: alvos visíveis ≥44 × 44 px, formulários móveis em uma coluna, sem overflow da página; gestão/técnico, 360/760 px e desktop |
| Documentação | PASSOU: destinos locais dos links existentes |
| Preservação de escopo | PASSOU: backend, migrações, testes de segurança, dependências, licenças e infraestrutura sem alteração |
| Marca oficial | NÃO VERIFICÁVEL (arquivo da logo ausente); paleta e nome textual são provisórios |

Restauração completa, inferência real, dispositivo físico e produção:
**NÃO EXECUTADO nesta validação**. Instruções documentadas não representam homologação.

Descontinuação nativa publicada em [feed935](https://github.com/matheusenalt/SolDesk/commit/feed935fb553d8346fddfa80672206bd9eabab05).
[GitHub Actions aprovado](https://github.com/matheusenalt/SolDesk/actions/runs/43979286026)
para esse commit. Migrações até `0006a` e controles de API preservados; Android
anterior não foi aprovado, foi descontinuado. Saneamento documental publicado em
[eba2566](https://github.com/matheusenalt/SolDesk/commit/eba2566429dad36bb380e679b4f47f72b2709218),
com [Actions aprovado](https://github.com/matheusenalt/SolDesk/actions/runs/43982343154).
Paleta/responsividade publicadas em [cfa7250](https://github.com/matheusenalt/SolDesk/commit/cfa7250b794114771b9da2ffdf189710a1131f23), com [Actions aprovado](https://github.com/matheusenalt/SolDesk/actions/runs/44095281109);
não declarar a identidade definitiva concluída sem a logo oficial.

## Gravação web e base PWA — validação em 17/11/2026

Implementado: pausa/continuação compatível, prévia e descarte, recusa de arquivo
vazio, avisos de falta de microfone/formato/interrupção e conteúdo local não salvo.
Recuperação de resposta perdida conserva a chave de criação; duplo envio é
bloqueado e o upload reutiliza a deduplicação do servidor. Registro salvo pode ser
aberto após upload recusado. Processado não significa validado por uma pessoa.
Manifesto inicial existe com MIME correto; não há service worker ou modo offline.
Ícones e instalação homologada permanecem pendentes da logo oficial.
Operação e limites: [mídia](docs/OPERACAO_MIDIA.md).

| Verificação atual | Resultado |
|---|---|
| Backend isolado PostgreSQL/Redis/ffmpeg | PASSOU: 72 testes, 1 aviso Starlette/httpx |
| Unitários web | PASSOU: 6 testes |
| Ruff/ESLint, formatação, TypeScript/build e Compose | PASSOU |
| Foco em áudio e recuperação | PASSOU: 28 cenários; cenário worker repetido separadamente: 2 PASSOU |
| Suíte autenticada completa final | PASSOU: 54 cenários em 3,8 min, sem skips; desktop e emulação móvel |
| Instalação pública e manifesto/CSP | PASSOU: 4 cenários |
| Cache após sessão autenticada | PASSOU: Cache Storage vazio, zero service workers, local/sessionStorage vazios; clientes, registro, processamento e relatórios com no-store |
| Banco | PASSOU: suíte em banco isolado, revisão 0006a; nenhuma migração nova |

Problemas encontrados: Docker estava parado; primeira rodada iniciou antes de o
servidor dev ficar disponível. Manifesto faltava no volume de desenvolvimento e
estava com MIME genérico no Nginx; ambos corrigidos. Recuperação de upload podia
disputar a revisão com o worker; releitura e uma tentativa adicional implementadas.
Um seletor de teste não considerava o prefixo do alerta e foi corrigido. Vitest foi
bloqueado pelo sandbox na leitura de diretórios ancestrais: repetido com sucesso
fora dessa restrição. Primeira suíte completa teve 53 PASSOU e um timeout durante
reinicialização concorrente do frontend; cenário afetado repetido: 2 PASSOU.
A repetição completa final teve 54 PASSOU, sem reconstruções concorrentes.

| Navegador | Dispositivo/ambiente | Resultado e limite |
|---|---|---|
| Microsoft Edge/Chromium | Windows, desktop automatizado; microfone fictício | PASSOU nos cenários focados de gravação, pausa, envio, recuperação e interrupção simulada |
| Microsoft Edge/Chromium | Pixel 7 emulado no Windows; microfone fictício | PASSOU nos mesmos cenários focados; não equivale a Android físico |
| Chrome/Firefox/Safari | Desktop independente ou aparelho físico | NÃO EXECUTADO nesta validação |
| Safari iOS / Chrome Android | Celular físico e microfone real | NÃO EXECUTADO |
| Instalação PWA | Dispositivo físico | NÃO VERIFICÁVEL (ícones oficiais ausentes); manifesto não representa homologação de instalação |

Silêncio exige escuta humana; não há detector automático. beforeunload não garante
aviso ao encerrar aplicativos móveis. Sem rascunho offline, inferência real ou teste
de HTTPS remoto/produção. Upload continua 25 MiB por padrão/teto 64 MiB; 80 MB pendente.
Implementação atual aguarda revisão, **sem commit/push próprio**.
