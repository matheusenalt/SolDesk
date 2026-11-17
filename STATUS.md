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
- API de fidelidade independente: versão material/hash exatos, conferência por leitor
  autorizado, histórico imutável e pendências; interface específica ainda pendente.

- API de atendimentos contínuos: mesmo ID, atualizações com datas próprias,
  retomada, transferência e finalização; atividade interna sem cliente artificial.
  Histórico, controle de revisão/idempotência e isolamento por empresa testados.
## Parcial ou com limitações

- Paleta provisória, ações principais e responsividade ajustadas; **identidade
  definitiva pendente da logo oficial**, não localizada. Nenhuma logo foi recriada.
  Ver [identidade e medições](docs/IDENTIDADE_SOL.md).
- Mock reutiliza texto humano; **não reconhece fala**. faster-whisper opcional existe,
  mas inferência/qualidade/desempenho reais não foram homologados.
- Finalização ainda exige cliente. A API já oferece validação independente por versão;
  a interface específica permanece pendente. A confirmação operacional legada foi preservada.
- Sistema/software é texto, não catálogo; busca é de clientes/artigos, não global.
- Chamados não possuem todo o fluxo futuro de prazo/aceite/inatividade; equipe serve
  aos relatórios. Relatórios são limitados em memória e não têm benchmark produtivo.
- Upload padrão 25 MiB, teto 64 MiB; 80 MB não suportados. Sem quotas/streaming completo.
- Restauração, HTTPS/privacidade de produção, carga e auditoria independente pendentes.
  Ver [limitações](docs/LIMITACOES.md), [segurança](docs/SEGURANCA.md), [backup](docs/BACKUP.md).

## Planejado — não implementado

Atendimento contínuo/atividade interna; interface da validação independente; catálogo de sistemas;
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
Gravação web/base PWA publicadas em [0a8c1d2](https://github.com/matheusenalt/SolDesk/commit/0a8c1d2e2fef2c45a9d4c60d3a8bc2620050a679), com [Actions aprovado](https://github.com/matheusenalt/SolDesk/actions/runs/44101292033).

## Fidelidade independente — dados e API

Implementado: RecordContentVersion/ContentValidation; SHA-256 do conteúdo canônico,
versão material, autor de origem, pessoa/data da validação e histórico append-only.
Uma nova edição ou transcrição deixa a versão corrente não validada. Voltar ao mesmo
texto não reaproveita aprovação de uma versão anterior. Salvar/processar não exige
validar; a conferência não conclui, confirma operacionalmente ou reabre chamados.
As regras anteriores de edição/confirmação e suas triggers foram preservadas.

API permite validar o próprio texto ou o de outro autor quando o usuário já pode
consultar o registro. Essa é a política inicial para revisão por Matheus; não exige
segunda pessoa. Escopo sempre vem da sessão e inclui autorização por objeto.
Contratos: [API de registros](docs/API_ATENDIMENTOS.md), [permissões](docs/PERMISSOES.md).

| Verificação atual | Resultado |
|---|---|
| Suíte backend completa final | PASSOU: 83 testes, 1 aviso Starlette/httpx |
| Validação independente/upgrade focados | PASSOU: 10 cenários de validação e 1 de migração; inclui concorrência, idempotência, terceiro autorizado, hash e RLS |
| Upgrade real 0006a → 0009 | PASSOU: banco novo no cluster de testes; duas empresas, fatos/versões anteriores preservados, nenhuma validação inferida |
| Downgrade seguro | PASSOU: reversível com tabelas novas vazias; bloqueado antes de descartar histórico existente |
| Banco local de desenvolvimento | PASSOU: migração aditiva aplicada, revisão 0009, API anuncia text_validation e preserva protocolo legado |
| Ruff/ESLint, formatação e TypeScript/build | PASSOU |
| Unitários web | PASSOU: 6 testes |
| Regressão autenticada no navegador | PASSOU: 54 cenários, sem skips, em 3,5 min; desktop/emulação móvel com API atualizada |
| Smoke público | PASSOU: 4 cenários com API atualizada |
| Interface nova de fidelidade | NÃO EXECUTADO: implementação reservada à Parte B |

Problemas encontrados: preparação do teste de legado sem name_key e comparação
entre contratos PATCH/GET diferentes, ambos corrigidos. A primeira suíte completa
teve 81 PASSOU/2 FALHOU: server-info listava revisões antigas; incluída 0009 e
preservadas as capacidades. Foco repetido: 3 PASSOU; suíte final: 83 PASSOU.
Após recriar a API local, o proxy Nginx precisou recarregar sua resolução interna.
Antes dessa estabilização, houve 3 falhas de login e 51 cenários aprovados;
repetição focada: 8 PASSOU; repetição completa final: 54 PASSOU.
Não houve alteração de banco/serviço de produção, instalação de modelo ou deploy.

Limitações: interface, etiquetas e revisão individual na web ainda pendentes;
histórico individual sem paginação. Legado começa sem validação neste eixo, mesmo
quando já confirmado operacionalmente. Ícones/logo e testes físicos seguem pendentes.
Sem nova dependência ou serviço. Parte A publicada no commit 2ba85f2 em 17/11/2026;
push concluído e GitHub Actions aprovado. Parte B adiada por solicitação de avanço.

## Atendimentos contínuos — dados/API (17/11/2026)

Implementado: extensão operacional Attendance reutiliza Record/revisões/áudio;
ciclo em_andamento/aguardando_retomada/finalizado, consulta de pendências vencidas,
passagem de turno, resultado e atualizações preservadas. Finalizar não valida texto.
Atividade interna funciona também na finalização existente; API e banco exigem
cliente ou marcador interno. Relatórios aceitam cliente ausente sem inventar cadastro.
Interface de atendimentos e interface de fidelidade independente seguem pendentes.

| Verificação | Resultado |
|---|---|
| Backend completo com PostgreSQL/Redis/ffmpeg isolados | PASSOU: 93 testes, 1 aviso upstream Starlette/httpx |
| Ciclo e migração focados | PASSOU: abertura, histórico, áudio/retry, permissões, conflitos e idempotência |
| Migração 0010 / legado / duas empresas | PASSOU: fatos e revisões preservados; RLS nova tabela comprovada |
| Reversão segura | PASSOU: extensão vazia reverte; existência de atendimento impede reversão antes de remover dados |
| Ruff / formatação backend | PASSOU: 50 arquivos verificados |
| ESLint / formatação / TypeScript / Vite | PASSOU |
| Unitários web | PASSOU: 6 testes |
| Docker local | PASSOU: imagens reconstruídas, migração aditiva aplicada e serviços saudáveis; API anuncia attendances |
| Navegador autenticado | PASSOU: 54 cenários (6,1 min); mais 6 focados após proteção final (1,2 min) |
| Smoke público | PASSOU: 4 cenários, desktop e móvel emulado |
| Reconhecimento real de fala | NÃO EXECUTADO: sem instalar modelo; mock e provedor controlado não comprovam ASR |
| Interface nova | NÃO EXECUTADO: reservada à Parte B |

Problemas corrigidos durante validação: invocação inicial de pytest fora do módulo
não utilizava corretamente o código montado; padronizado python -m pytest.
Teste de áudio passou a distinguir erro esperado do mock sem texto e sucesso de
provedor controlado com retry. Teste de reversão recriava tabela sem reaplicar
privilégios; corrigido para usar o comando de migração completo do projeto.
Lint apontou ordem de import e linha longa, ambos corrigidos. Revisão final bloqueou
derivação legada fora do ciclo; 19 testes focados PASSOU. Resultado completo
backend final repetido após proteção: 93 PASSOU em 3 min 20 s, sem falhas ou skips. Nenhuma dependência nova; AGPL preservada.
Sem mudança em produção, instalação de modelo ou deploy. Parte atual sem commit/push.

Publicação anterior: [2ba85f2](https://github.com/matheusenalt/SolDesk/commit/2ba85f2622852ea84786b52ddbc11d986052b7ee),
push concluído e [GitHub Actions PASSOU](https://github.com/matheusenalt/SolDesk/actions/runs/44111577983).
Parte B da validação independente foi adiada por solicitação de avanço.

Documentação: 126 links locais PASSOU. Revisão dos 21 arquivos alterados: nenhum
padrão de segredo encontrado; stage vazio, licença oficial e exclusões preservados.
Parte A pronta para revisão; Parte B não iniciada. Nenhum aceite automático de fase seguinte.

## Interfaces de validação e atendimentos — situação atual

Implementado: painel de atendimentos com listas paginadas de em andamento,
aguardando retomada, finalizados recentes e pendências de passagem de turno;
abertura por Finalização ou Em andamento, atividade interna explícita, atualização,
transferência, próxima ação, retomada e conclusão. Texto e áudio usam o pipeline
existente; reenvio preserva chave e registro salvo. Datas são exibidas no fuso da empresa.
Fidelidade tem etiquetas, fila própria, versão exata, conferência individual sem
pré-seleção, Validar agora/depois, histórico e recuperação de falhas. Outro leitor
autorizado valida pela web. Correção exige nova conferência sem mudar o ciclo.
Não existe botão de validação coletiva; confirmação operacional legada é independente.

- PASSOU: 6 cenários novos focados em desktop e móvel emulado, inclusive resposta
  perdida, outro leitor, erro recuperável e histórico após correção.
- PASSOU: backend completo 93 testes, 1 aviso upstream; ESLint/formatação,
  6 unitários web e TypeScript/Vite. Editor sem erros.
- PASSOU: regressão completa final de navegador, 60 cenários, 4,7 min.
- Sem migração adicional, dependência nova, serviço externo empresarial ou produção.
- Limitações mantidas: mock não reconhece fala; ASR real, dispositivos físicos,
  logo/ícones oficiais e instalação PWA não foram homologados nesta entrega.
Esta seção substitui as pendências de interface das entregas anteriores.

Na primeira regressão completa: 56 PASSOU / 4 FALHOU. As novas seleções não
tinham nome acessível exato; corrigido com aria-label centralizado, sem reduzir
as verificações. Repetição focada: 4 PASSOU em desktop/móvel. Suíte final: 60 PASSOU, sem falhas ou skips.

Fechamento autorizado em 17/11/2026: interfaces 09B e 10B aprovadas pelos testes
acima e incluídas no conjunto da etapa 10. Implementação validada, pronta para
publicação pelo fluxo do projeto antes do catálogo. Demais limitações permanecem.
## Catálogo de sistemas — Parte A, 17/11/2026

**Funciona agora:** API de catálogo por empresa, nomes normalizados únicos,
ativação/inativação, vínculos N:N cliente/sistema com versão e observações,
seleção e filtros em registros, atendimentos, chamados, conhecimento e relatórios.
Texto legado preservado; classificação manual assistida com sugestões, aceite ou
rejeição explícitos, revisão, idempotência e histórico. Não há vínculo automático.
**Parcial:** catálogo disponível pela API; gerenciamento web, combobox acessível e
reconciliação visual aguardam a Parte B. Nenhuma implementação da etapa seguinte.

| Verificação executada | Resultado |
|---|---|
| Backend completo PostgreSQL/Redis/ffmpeg isolados | PASSOU: 106 testes, 179,20 s; 1 aviso upstream Starlette/httpx |
| Catálogo, concorrência, idempotência, migração e fidelidade focados | PASSOU: 24 testes na última rodada focada |
| Migração 0011 com legado e duas empresas | PASSOU: dados anteriores intactos, RLS e FKs; reversão vazia e bloqueio com dados novos |
| Ruff e formatação Python | PASSOU: 55 arquivos |
| ESLint, formatação, TypeScript e Vite | PASSOU |
| Unitários web | PASSOU: 6 testes |
| Docker local | PASSOU: imagens reconstruídas; desenvolvimento confirmado; revisão 0011; API anuncia systems |
| Navegador autenticado: ciclos, conhecimento, relatórios e chamados | PASSOU: 20 cenários desktop/móvel emulado, 2,3 min |
| Smoke público local | PASSOU: 4 cenários, 35,3 s |
| Documentação | PASSOU: links locais conferidos; contrato e guias atualizados |
| Interface do catálogo, ASR real e dispositivos físicos | NÃO EXECUTADO: fora desta Parte A |

Nenhuma dependência nova, modelo instalado, banco de produção ou serviço empresarial
acessado. Migração aditiva; seleção guarda instantâneos e preserva horários do fato.
Classificação material exige nova validação de fidelidade, mantendo as anteriores.
Problemas corrigidos na implementação: conflito de revisão em edição concorrente,
preservação de espaços do legado e compatibilidade da idempotência sem system_id.
Na revisão documental, linhas em branco extras foram corrigidas. Limitações de logo,
PWA, reconhecimento real de fala e restauração homologada continuam existentes.

Publicação anterior concluída: [bf2fb0b](https://github.com/matheusenalt/SolDesk/commit/bf2fb0be1803b1da753ce83686aae30b87574ad7),
push OK e [GitHub Actions PASSOU](https://github.com/matheusenalt/SolDesk/actions/runs/44124050455).
A Parte A atual permanece sem commit/push, aguardando revisão. A etapa completa
depende da Parte B. [Contrato e testes do catálogo](docs/API_SISTEMAS.md).
