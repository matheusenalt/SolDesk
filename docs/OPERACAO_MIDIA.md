# Operação de áudio e armazenamento


O padrão é mock offline: reutiliza apenas relato humano e não reconhece fala.
Texto continua funcionando sem transcrição. Para operação textual, pare os workers
de áudio, configure `TRANSCRIPTION_PROVIDER=disabled` e repita o setup; upload de
áudio informa indisponibilidade. Redis/dispatcher continuam no Compose padrão.
Ao trocar provedor, pare o worker antigo antes de iniciar o novo: não misture
provedores consumindo as mesmas filas. Não há reconhecimento real homologado.

Saúde autenticada: `/api/v1/media/health`. Probe do worker:
`docker compose exec worker python -m app.media_worker health`.
Uploads respondem antes da transcrição; arquivo e recibo ficam persistidos.
Fila indisponível não deve impedir encaminhar/resolver chamado urgente.
Retenção padrão mantém arquivos; remoção por política explícita preserva
metadados e histórico, e precisa abranger cópias/S3/backups conforme política.

## faster-whisper opcional

Não está no modo rápido e não instala pesos por padrão. Obtenha explicitamente um
modelo CTranslate2 com licença/procedência verificadas; coloque seus arquivos em
`models/whisper` (ignorado pelo Git). Ausência do modelo causa erro amigável/retry,
sem download. Semear áudio fictício e revisar manualmente também neste modo.

1. `docker compose stop worker`
2. Ajuste `TRANSCRIPTION_PROVIDER=faster_whisper` em `.env`.
3. Repita setup ou use `docker compose --profile whisper up -d --build --wait api dispatcher worker-whisper`.
4. `docker compose exec worker-whisper python -m app.media_worker health`.
5. `docker stats --no-stream` para CPU/RAM; registre modelo/hardware, duração do
   áudio, tempo de carga/processamento, memória de pico e precisão em português.

Imagem limitada a 2 CPUs/3 GiB e tmpfs 128 MiB; inferência CPU/int8, duas threads,
`HF_HUB_OFFLINE=1`, modelo montado somente leitura e `local_files_only=True`.
Imagem construída/importada e recusa de modelo ausente testadas sem rede;
**inferência e benchmark com modelo real permanecem pendentes**, sem promessa de
velocidade. Para voltar, pare worker-whisper, ajuste mock e repita setup.

## S3 compatível e antivírus opcionais

Configure no ambiente do servidor ou `.env` ignorado `STORAGE_BACKEND=s3`, endpoint,
bucket privado sem versionamento, região e chaves próprias. Perfil de exemplo
RustFS usa `http://object-store:9000` e as chaves `S3_ACCESS_KEY`/`S3_SECRET_KEY`,
vazias no exemplo; não há senha fixa, console nem porta no host.

```text
docker compose --profile s3 up -d --wait object-store
docker compose run --rm migrate python -m app.media_worker storage-init
docker compose run --rm migrate python -m app.media_worker storage-check
```

`storage-init` cria bucket privado se ausente, sem política pública. `storage-check`
escreve/lê/remove exclusivamente um objeto fictício novo. Repita setup para aplicar
o backend à API/dispatcher/worker. Para AWS ou MinIO existente, configure endpoint
HTTPS apropriado, bucket e IAM restrito; o perfil local não é exposição de produção.
Trocar backend/bucket não migra objetos existentes. Backups/versões de S3 exigem
lifecycle próprio. O adapter foi testado com RustFS real; MinIO não foi iniciado
(imagem tentada retornou 401). Dados locais existentes não foram apagados.

ClamAV: `docker compose --profile antivirus up -d clamav`, espere inicializar
assinaturas, ajuste `CLAMAV_ENABLED=true` e repita setup. Desligado por padrão.
O hook INSTREAM foi testado com servidor TCP controlado (limpo/FOUND); daemon e
atualização real de assinaturas não foram homologados.

Ditado Web Speech: admin precisa habilitar, navegador precisa suportar contexto
seguro e usuário aceitar o aviso **antes** de ativar. Alguns fabricantes recebem
áudio em seus serviços; não ative para dados privados. Não opera simultaneamente
com MediaRecorder. Texto ao vivo fica separado do resultado do servidor. Serviço
real do fabricante/Safari/iOS/aparelho físico não foram testados; fallback permanece.

Estado de validação e pendências: [STATUS](../STATUS.md).


Contrato: [API de mídia](API_MIDIA.md). Limites: [limitações](LIMITACOES.md).

## Gravação e recuperação no navegador

O React usa `getUserMedia` e `MediaRecorder`. Detecta WebM/Opus, Ogg/Opus ou
MP4 antes de iniciar; pausa/continuação aparecem somente quando disponíveis.
O limite de duração vem de `/media/settings` (padrão 600 s). Digitação e escolha
de arquivo continuam disponíveis quando falta permissão, dispositivo ou formato.
Ao parar, o áudio permanece apenas em memória, com prévia para escuta e descarte.
Arquivo vazio é recusado; silêncio deve ser identificado pela escuta humana:
não há detector automático nem garantia de qualidade. Interrupção conserva a prévia
disponível e mostra aviso; arquivo incompleto pode ser recusado pelo servidor.

O aviso de saída usa `beforeunload`, sujeito às restrições do navegador, sobretudo
em celulares. Trocar de área ou encerrar o navegador pode perder o conteúdo local;
não existe rascunho persistido automaticamente, sincronização offline ou envio em
segundo plano. O ditado experimental pode depender do fabricante e continua opt-in.

O formulário envia primeiro `POST /records` com chave de idempotência; depois
envia os bytes a `/records/{id}/audio?revision=...`. O servidor persiste o arquivo
privado, vínculo e job antes de depender do worker. Registro salvo e áudio aceito
são operações separadas: uma falha no upload não desfaz o registro já criado.
Uma resposta perdida mantém a chave e bloqueia edição até recuperar a tentativa.
O reenvio usa os mesmos bytes; SHA-256/lock no servidor evitam outro arquivo/job.
Conflito 409 no upload permite uma releitura da revisão e uma tentativa adicional,
sem alterar o texto. Quando o ID salvo é conhecido, é possível abrir esse registro
e descartar apenas a prévia local, inclusive após recusa de tamanho/formato.

O processamento segue assíncrono (Redis/RQ, dispatcher e worker/ffmpeg).
Mock não reconhece fala. `Attachment.validated` indica validação técnica do arquivo;
texto processado continua exigindo revisão humana. A validação independente por
versão permanece planejada. Limites de 25 MiB por padrão/teto 64 MiB não mudaram;
anexos de 80 MB dependem de etapa própria de streaming, quotas e proteção contra abuso.

## Base PWA e privacidade

Existe manifesto com nome, idioma, escopo e cores provisórias. Ícones oficiais e
homologação de instalação permanecem pendentes da logo. Não há service worker,
Cache Storage da aplicação, armazenamento local de registros ou operação offline.
Falha de conexão exige tentar novamente com a página ainda aberta.
A API preserva `Cache-Control: no-store`; CSP e política de permissões não foram
relaxadas. HTTPS é obrigatório para microfone remoto; localhost é exceção de
desenvolvimento. HTTP por IP da rede não equivale a um contexto seguro.

A matriz de testes e suas limitações está em [STATUS](../STATUS.md).
