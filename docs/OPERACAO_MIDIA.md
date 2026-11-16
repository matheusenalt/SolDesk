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
