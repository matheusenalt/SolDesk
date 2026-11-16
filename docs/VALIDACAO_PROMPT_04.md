# Validação da Fase 04 — áudio, arquivos e processamento

Data: 16/11/2026. Escopo do [Prompt 04](../SolDesk_Prompts_v2/04_Audio_Transcricao_Templates_e_Processamento.md).
Ambiente local Windows/PowerShell, Docker Desktop/WSL 2, PostgreSQL 17, Redis 8,
Python 3.13.16, Node 22.23.5, navegador Edge headless desktop/emulação móvel.
Somente empresas, pessoas, textos e áudio fictícios; nenhum áudio pessoal capturado.

## Implementado

- StorageBackend local privado/S3 compatível, Attachment com um dono por empresa,
  upload em cliente/chamado, formatos/assinatura/MIME/tamanho, hook AV opcional,
  URLs HMAC curtas vinculadas à sessão e auditoria de abertura.
- Gravação real MediaRecorder, permissão/contador/prévia/cancelamento/regravação,
  envio de áudio/arquivo e digitação; aviso de contexto seguro e fallback.
- Upload 202, recibo durável PostgreSQL, RQ/Redis, worker/dispatcher, urgência,
  leases/idempotência, retries com backoff/timeout, reprocessamento/descarte.
  ffmpeg só no worker; WAV, WebM, Ogg, M4A, AAC e MP3 exercitados.
- Mock determinístico offline explícito, sem inventar texto de fala; contrato de
  provedor e faster-whisper opcional CPU/int8/local. Nenhum modelo baixado.
- Textos bruto/normalizado/organizado/humano separados; incerteza/possível
  credencial sinalizadas, templates versionados por tipo/empresa, glossário de
  palavras, revisão humana, notificação interna e retenção auditada.
- Fato/recebimento preservados, finalização volta à revisão, conhecimento não
  publica, urgente é resolvido com worker parado e recebe comentário depois.
- Protótipo Web Speech opt-in com aviso de fabricante, desligado por organização;
  contrato JSON fundamentado para organizador LLM futuro (somente rules entregue).

Código principal: [media_routes](../backend/app/media_routes.py),
[worker](../backend/app/media_worker.py), [storage](../backend/app/storage.py),
[transcription](../backend/app/transcription.py),
[migração 0004](../backend/migrations/versions/0004_media.py),
[AudioCapture](../web/src/AudioCapture.tsx), [MediaPanels](../web/src/MediaPanels.tsx),
[WorkArea](../web/src/WorkArea.tsx), [Compose](../compose.yaml).
Contratos e fronteiras: [API_FASE_04](API_FASE_04.md).

## Testes executados e resultados

| Validação | Resultado local observado |
| --- | --- |
| `docker compose --profile test run --build --rm tests` | 43 pytest aprovados; repetição final com imagem já construída: 49,95 s, sem skip no perfil PostgreSQL |
| `npx playwright test --config playwright.identity.config.ts` com `E2E_CONTROL_WORKER=1` | 24 aprovados em 2,2 min; sem skip; 12 cenários × desktop/emulação móvel |
| `npm test` | 6 Vitest aprovados |
| `npm run test:e2e` contra Nginx/API | 4 regressões de instalação aprovadas em 9,8 s |
| `npm run lint`, `npm run format:check`, `npm run build` | ESLint, Prettier, TypeScript e Vite aprovados |
| Ruff check/format de backend e scripts | Aprovados, 31 arquivos formatados |
| `python scripts/tokens.py --check` | 32 pares de contraste e geração sem deriva aprovados |
| `scripts/setup.ps1` + `scripts/test-compose.ps1` | Build/saúde, migrações repetidas, UUID persistente após restart, proxy/OpenAPI, não root e volume PostgreSQL sem porta aprovados |
| `bash -n scripts/setup.sh` | Sintaxe aprovada; execução Bash remota será verificada no Actions |
| S3 real privado (RustFS), `storage-init` + `storage-check` | Put/get/delete com bytes iguais e remoção exclusiva do objeto fictício aprovados; chaves aleatórias só no ambiente |
| Imagem opcional worker-whisper | Build aprovado, extras instalados e importados; validação sem rede de modelo local ausente recusado, sem download |
| Perfil dev | API/Vite reconstruídos e iniciados; API normal sem ffmpeg, worker com ffmpeg 7.1.5; hash do código da API igual ao arquivo revisado |
| Licenças e texto AGPL | Inventários base/opcionais revistos; hash oficial preservado, conforme [LICENCAS](LICENCAS.md) |

19 casos parametrizados novos somam-se às 24 regressões: regras e evidência
literal, glossário sem números, mock/tempos/revisão, anexos/dedup/hash/acesso e RLS,
extensão trocada/arquivo vazio/tamanho/provedor desativado, seis contêineres reais
gerados por ffmpeg, duração excessiva, timeout/backoff/retry/descarte, Redis/RQ
executando job urgente após resolução, versões/snapshot/retenção, S3 SDK privado,
A/B/expiração/outra sessão e lease invalidado, worker interrompido, ditado/retenção
por dias e hook ClamAV TCP limpo/FOUND.

Navegador cobre fluxo real de revisão/confirmação, marcação de incerteza/credencial,
download privado, gravação de microfone fictício do Chromium com upload do WebM
produzido, cancelamento e nova gravação, conhecimento rascunho, worker Docker
parado/retomado com Ticket resolvido, anexo no Ticket, edição visual de template,
glossário e recusa simulada de microfone seguida de envio textual. Mantidas as
regressões de identidade, equipe/clientes, relatos, lotes e chamados.

## Problemas encontrados e corrigidos

- Download de imagem MinIO retornou 401. Adaptador S3 foi mantido e o perfil
  opcional passou a RustFS fixado por digest; operação real comprovada, sem copiar
  código de terceiros nem inserir credenciais padrão.
- Fixture de autenticação anterior dependia de hook/cookies por arquivo e gerou
  401 ao ampliar a suíte. Agora login é fixture por worker e cookies são instalados
  em cada contexto, sem enfraquecer rate limit nem gravar credenciais/traces.
- A asserção do teste de recusa do microfone ignorava o prefixo visual de alerta;
  corrigida para conferir o conteúdo do alerta. A UI já exibia a mensagem correta.
- Relatos textuais passaram a fixar versão de template, não só os com áudio;
  idempotência de requisições da fase 03 preserva o hash quando não há ditado.
- Fila promove prioridade ainda aguardando; lease impede resultado descartado
  sobrescrever edição humana posterior; transcrição mock na conversa é identificada.

## Limites e pendências explícitas

- **Benchmark e reconhecimento real faster-whisper pendentes**: nenhum peso foi
  instalado, inferência não foi executada. Medir CPU/RAM/tempo/precisão por modelo
  antes de uso; não prometer velocidade. Essa pendência é prevista no Prompt 04.
- Web Speech do fabricante, Safari/iOS/Firefox, aparelho/microfone físicos e HTTPS
  de desenvolvimento não foram testados. Formatos de arquivo foram testados;
  emulação móvel não é teste de aparelho físico. Digitação/upload são alternativas.
- Antivírus real e atualização de assinaturas não executados; hook/protocolo
  testados com servidor controlado. Hook desligado por padrão.
- S3 AWS/MinIO em produção, backups/versionamento/replicação, TLS/provisionamento,
  limites em carga, pip-audit/gitleaks e auditoria independente não foram validados.
  Bucket deve ser privado e sem versionamento no fluxo de remoção atual.
- Aviso upstream de depreciação TestClient/httpx permanece; não houve falha.
- Nenhuma publicação automática/LLM externo, peso de modelo ou credencial incluído.
  Publicação/busca/relatórios são da Fase 05, ainda não iniciada.

## Revisão e publicação

Antes do commit: origin oficial conferido, main sincronizada com origin/main
(0 adiante/0 atrás), identidade Git configurada e diff revisado. Busca por padrões
de chaves privadas/tokens sem ocorrência nos arquivos publicáveis. `.env`, `.venv`,
`.tools`, node_modules, resultados/cache, mídia e modelos fora do conjunto do Git.
Locks preservados, nenhuma alteração de versão dos 42 pacotes Python anteriores;
LICENSE oficial com SHA-256
`0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0`.
Não foram acessados/copiados dados/fontes de outros projetos ou empregadores.
A busca textual não substitui auditoria independente.

Implementação: [`23b276adc84e81818f2f21453e03a33e79ce4e0f`](https://github.com/matheusenalt/SolDesk/commit/23b276adc84e81818f2f21453e03a33e79ce4e0f),
`feat: implementa fase 04 do SolDesk`. Push para main oficial concluído, avanço
normal de `0ae4189` para `23b276a`, sem force, main/origin main sincronizadas.
O [Actions da implementação](https://github.com/matheusenalt/SolDesk/actions/runs/43889397697)
terminou `completed/success`. Concluiu os passos de lint/formatação, testes rápidos, tokens, build, PostgreSQL,
setup Bash e navegador com sucesso. Logs do job PostgreSQL registram **43 pytest
aprovados em 29,20 s** e **24 Playwright aprovados em 1,8 min**, sem skip nessas
suítes; Chromium em Ubuntu, incluindo parada/retomada real do worker.
O job rápido pode pular testes exclusivos de PostgreSQL; eles foram executados
integralmente no job PostgreSQL, não contados como aprovados por terem sido pulados.
Nenhum aceite obrigatório do modo padrão permanece falhando/pendente. Inferência
real/benchmark e demais opcionais acima continuam sem aprovação presumida.
Parar antes do Prompt 05.
