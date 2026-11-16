# API legada de sessão por token

> Contrato legado preservado por compatibilidade. O cliente Android/iOS
> e o painel de QR foram descontinuados em 16/11/2026. Migração, rotas e
> garantias de segurança da API permanecem; a web usa cookie e CSRF.

Migração aditiva `0006a`. Sessões web continuam com cookies HttpOnly e CSRF;
sessões nativas usam exclusivamente `Authorization: Bearer <access_token>`.
Não combinar cookie de sessão com bearer. Um token web não autentica como mobile
e um bearer mobile não autentica como cookie. Todas as permissões de negócio,
filtros de organização, revisões, RLS e erros `application/problem+json` continuam.

## Identificação pública, antes de autenticar

`GET /api/v1/server-info` acrescenta `instance_name` (configuração pública
`SOLDESK_INSTANCE_NAME`, não nome privado da empresa), `mobile_protocol_version: 1`
e capacidade `mobile_auth` somente no esquema migrado compatível. A versão da
API continua `1.0.0`; protocolo mobile é negociado separadamente.

## Autenticação mobile

| Rota | Corpo e resultado |
|---|---|
| `POST /api/v1/mobile/auth/login` | `{email, password}`. Mesmos Argon2id e limitadores persistentes do login web. Primeira associação ativa, ordenada por organização; Community tem uma organização. |
| `POST /api/v1/mobile/auth/refresh` | `{refresh_token}`. Rotação de uso único, revogando o acesso anterior. Reutilização revoga a família inteira, inclusive sob concorrência. |
| `POST /api/v1/mobile/auth/logout` | `{refresh_token}`. Revoga a família; retorna 204. Independe de acesso ainda válido. |
| `POST /api/v1/mobile/auth/password` | Bearer e `{current_password, new_password}`. Inclui troca de senha temporária. Revoga sessões anteriores do usuário e retorna um par novo. |

Login/refresh/senha retornam `token_type: "Bearer"`, `access_token`, `refresh_token`,
`acesso_expira_em` e `renovacao_expira_em`. Acesso: 15 minutos; refresh: prazo
absoluto de 30 dias, que não se estende a cada rotação. Sem cookies nessas respostas.
Banco guarda somente hashes SHA-256 de segredos aleatórios de alta entropia.
Desativação do vínculo, troca de senha e logout global impedem a renovação.
Ausência/falha/replay/expiração retorna 401; limitação retorna 429.

A tabela MobileRefreshToken tem RLS FORCE por organização **e usuário**. A função
de contexto com privilégio elevado tem search_path fixo, acesso público revogado
e retorna somente empresa/usuário para o hash exato de um refresh. Validade e
rotação são verificadas sob lock transacional por família. Runtime não recebe
permissão de apagar histórico nem credenciais em texto no banco.

Clientes externos devem proteger os tokens e tratar perda da resposta de refresh:
repetir um token já consumido revoga a família. Isso pode exigir novo login.

## Negócio reutilizado

Clientes, registros, revisão, chamados, conhecimento e notificações usam as rotas
de identidade, registros, mídia e conhecimento. Mutação bearer válida dispensa CSRF de cookie, mantendo contexto
e autorização de cada rota. Fluxos web de login/senha/criação ou seleção de empresa
são recusados com bearer; clientes usam as rotas explícitas de token.

Texto: `POST /records`, `submit: true`, Idempotency-Key e capturado_em estáveis no
reenvio manual do mesmo conteúdo. Áudio: registro primeiro, depois bytes m4a/AAC
em `POST /records/{id}/audio?revision=...`, MIME `audio/mp4`, X-Filename.
Chamado urgente é encaminhado antes do upload/processamento. Confirmação do autor
preserva ocorrido_em; conhecimento continua sujeito à revisão editorial humana.

## Compatibilidade

Os caminhos públicos com `mobile` e a migração `0006a` permanecem por
compatibilidade. O cliente nativo foi descontinuado; não há SDK, QR de
instalação, push remoto ou fila offline distribuídos. A web usa cookie/CSRF.
