# API de mídia e processamento

Todas as rotas abaixo usam `/api/v1`, sessão opaca e organização autenticada no
servidor; mutações exigem `X-CSRF-Token`. Respostas de erro seguem RFC 7807.
Não há ID de empresa no corpo para escolher tenant, nem credencial de S3 no cliente.

## Upload e acesso privado

| Rota | Comportamento |
| --- | --- |
| `POST /records/{id}/audio?revision=N` | Autor, revisão atual, corpo binário bruto; responde 202 com attachment/job/record |
| `POST /files/client/{id}` ou `/files/ticket/{id}` | Corpo binário bruto, responde 201; exige acesso ao dono |
| `GET /files/{owner_type}/{id}` | Lista até 100 anexos acessíveis, inclusive `record`; nunca retorna chave/caminho de storage |
| `POST /attachments/{id}/link` | Emite URL relativa assinada; validade padrão 120 s |
| `GET /attachments/{id}/content?expires=...&signature=...` | Exige a mesma sessão, vínculo, acesso ao dono e assinatura válida; audita abertura |

Envie nome original em `X-Filename` codificado com `encodeURIComponent` e MIME
em `Content-Type`. Não é multipart. Nome só é metadado; barra, controle e tamanho
excessivo são rejeitados. Limite padrão 25 MiB; a API limita bytes durante a leitura.
Nginx impõe teto adicional de 64 MiB com erro JSON. Identificação usa assinatura,
extensão e MIME coerentes; anexos permitidos: PDF, PNG, JPEG e texto UTF-8.
Áudio: WAV, WebM/Opus, Ogg, MP4/M4A, AAC e MP3. O worker exige apenas streams de
áudio, normaliza WAV mono 16 kHz e mede a duração efetiva (padrão até 600 s).
Validação de duração/contêiner é assíncrona; arquivo de áudio não é liberado para
download até passar. Uma extensão trocada não basta para autorizar o conteúdo.

Hash SHA-256 e lock transacional deduplicam o mesmo conteúdo por empresa/dono;
não dão acesso entre donos. `Attachment` tem exatamente um dono com FK composta
por empresa. Chave `organization_uuid/object_uuid`, sem nome original. Volume
privado fora do estático; S3 sem política/ACL pública criada pelo SolDesk.
Assinatura HMAC vincula empresa, usuário, hash da sessão, arquivo e expiração
(teto 300 s); ID ou URL isolados não autorizam. Respostas usam no-store/nosniff e
CSP sandbox; anexo é download, áudio validado admite reprodução inline.

O hook ClamAV INSTREAM é opcional; ligado, falha de conexão impede upload com
503. A auditoria guarda IDs, tamanho e hash, sem conteúdo, URL assinada ou segredo.
O nome original e o conteúdo continuam privados e devem usar somente dados
fictícios neste ambiente de desenvolvimento.

## Processamento e revisão

| Rota | Comportamento |
| --- | --- |
| `GET /records/{id}/processing` | Registro atual e últimos 20 jobs, textos, segmentos, avisos, template e tempos |
| `POST /audio-jobs/{id}/retry` | `{revision}`; autor cria novo job ligado ao anterior, com template/glossário atuais |
| `POST /audio-jobs/{id}/discard` | `{revision}`; autor invalida resultado pendente, remove áudio e volta à digitação |
| `GET /media/health` | Disponibilidade real Redis/heartbeat worker/dispatcher; não implica precisão de transcrição |

PostgreSQL é o recibo durável. Dispatcher varre a cada 2 s; RQ JSON transporta só
IDs opacos. Filas `audio-urgente` antes de `audio-normal`; mudança de prioridade
promove job ainda aguardando. Lease, locks e índice de job ativo impedem aplicar
duas vezes um resultado; cópia antiga na fila é inócua. Retry automático limitado
a 3 tentativas com espera 10/20 s; formato/duração inválidos são terminais. Timeout
padrão 300 s; interrupção abrupta é recuperada pelo dispatcher após timeout + 30 s.
Botão Reprocessar cria outro histórico, sem apagar o anterior. Confirmado,
publicado ou cancelado não recebe sobrescrita tardia. Logs não contêm transcrição,
credenciais, argumentos sensíveis ou stderr do ffmpeg.

Finalização/conhecimento concluídos voltam a `aguardando_revisao`. Confirmação de
finalização exige `audio_reviewed: true` na ação individual ou em cada item do
lote, revisão atual e texto conferido pelo autor; conhecimento não publica.
Mock sinaliza trecho incerto determinístico e reaproveita exclusivamente o relato
digitado: não interpreta a gravação. Registro somente de áudio no mock exige texto
manual antes de confirmar. Erro/fila parada nunca bloqueiam operações do Ticket;
transcrição posterior vira comentário `transcricao` ou `transcricao_mock`, sem
mudar descrição/estado, mesmo depois da resolução. Há notificação interna ao autor.

Separados: texto original, `ditado_texto` opt-in, transcrição bruta, normalizada,
organizada, edição humana/versionada, segmentos com confiança/incerteza, avisos por
offset e metadados do provedor/modelo/versão. `ocorrido_em` e `enviado_em` são
preservados; job registra início/fim e registro preenche `processado_em`.
Possível credencial é alerta para revisão, sem extrair valor secreto em novo campo.

## Templates, glossário e retenção

`GET /media/settings`, `GET /media/templates`, `GET /media/glossary` permitem
consulta autenticada. Somente admin usa `PATCH /media/settings`,
`POST /media/templates` e `POST /media/glossary`.

- Configuração: `{retention: manter|apos_confirmacao|apos_dias,
  retention_days: 1..3650, live_dictation_enabled: bool}`. Padrão manter, 30 dias
  quando escolhido prazo, ditado desligado. Limites/provedor são configuração do
  servidor; consulta nunca retorna chaves.
- Template: `{type, expected_version, fields: [{key,label,markers: [...]}]}`;
  concorrência rejeitada com 409, campos/marcadores únicos, só INSERT de versões.
  Três sementes por empresa; cada novo registro fixa a versão, primeiro upload
  a respeita e reprocessamento fixa nova versão sem alterar os jobs anteriores.
- Glossário: `{term, aliases: [...]}`; apenas palavras, sem números/códigos.
  Exemplos semeados Firebird, CFOP, Sintegra, SGBR e Cervantes. Normalização limita-se
  a grafias conhecidas; valores/códigos numéricos permanecem como informados.

Organizador entregue: `rules`, sob contrato `Organizer`. Usa somente marcadores
explícitos `Campo: texto`; fala livre permanece integral. Contrato do futuro `llm`
é `GroundedDraft`: `sections[{field,text,start,end}]`, campos permitidos e trechos
literais exatos da transcrição. Conteúdo sem evidência é rejeitado. Nenhuma
implementação LLM, chamada externa ou chave paga foi adicionada.

Limpeza a cada aproximadamente 60 s só remove áudio quando uma política explícita
o torna elegível e não há job ativo. Preserva metadados/textos/auditoria; padrão
`manter` não remove nada. Descarte solicitado pelo autor remove o objeto e registra
auditoria. S3 deve usar bucket privado **sem versionamento** neste fluxo: versões,
replicação e backups externos exigem política própria, não são apagados pelo SDK.
Trocar backend/endpoint/bucket não migra objetos antigos automaticamente.

Migração aditiva 0004 congela SQL, adiciona quatro tabelas com RLS FORCE, FKs
compostas, estados/índices e proteção do ditado original. Runtime não pode editar
templates antigos nem apagar auditoria. `media_organizations()` é SECURITY DEFINER
com search_path fixo e grant restrito: entrega só IDs para o dispatcher iniciar
cada contexto RLS; não entrega dados de negócio entre empresas.
