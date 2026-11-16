# Decisões

## Editorial e gestão descritiva

- Métricas escritas em [METRICAS](METRICAS.md) antes da implementação. Nenhuma
  medida de competência/complexidade, ranking de pessoas ou conclusão automática.
  Pessoa começa em ordem alfabética; reordenação manual é consulta, sem pontuação.
- Política editorial por empresa: administrador/gestor publicam por padrão;
  **autor publicar o próprio artigo fica desligado**. Admin pode habilitar e mudar
  papéis explicitamente. Publicação exige conferir conteúdo e avisos; devolução
  exige comentário. Nem IA nem worker publicam. Conteúdo não informado fica vazio/
  identificado, sem completar causa, procedimento ou código por suposição.
- Artigo geral ou restrito ao contexto de cliente. Restrito aparece na busca com
  cliente correspondente, cadastro e sugestões daquele cliente; não é ACL nova
  entre membros que já acessam todos os clientes da empresa. Fonte continua com
  autorização própria. Arquivar preserva versões; reabrir retira da busca até revisão.
- Busca PostgreSQL sem serviço novo: português/unaccent + trigramas + substring
  literal escapada para códigos. Trecho destacado é texto/offset, nunca HTML SQL.
  Semântica/pgvector fica para evolução. Aviso fiscal é heurística, não valida CFOP.
- Consultas editoriais não armazenam identidade do leitor. Agregado de gestão
  sem filtro pessoa/equipe; não atribuir leitura a técnico ou classificar leitores.
- Calendário/fuso atual da empresa, limites UTC semiabertos independentes;
  comparação anterior com igual quantidade de dias locais. Estado confirmado é
  o atual, agrupado pelo fato original; não fingir fotografia histórica da revisão.
- Registros por autor, ações por ator, atribuições por destinatário. Cada ciclo
  resolvido é amostra; reabertura mantém ticket único, encerrar é ação diferente.
  Mediana/P90/n; pausa é união recortada, sem dupla subtração. Nada de duração
  presencial/SLA presumido a partir de envio. Equipe/classificação são atuais.
- Distribuição por prioridade/categoria/sistema considera tickets únicos com
  ações do escopo/período, usando classificação atual; não explica causas.
- CSV usa mesmo escopo/filtros, BOM/aspas/apóstrofo para fórmulas e auditoria sem
  relato. Histórico completo dentro dos limites, sem truncar nas 100 linhas da UI.
  Conversão/regravação por planilha não é certificada universalmente.
- AGPL-3.0-only e condições de terceiros preservadas. Nenhum material privado de empregadores.
- Alteração de nome/fuso preserva políticas aninhadas;
  atualização do hash no mesmo documento abre artigo/origem sem exigir reload;
  filtro mantém cliente selecionado mesmo ao pesquisar outra lista de opções.
- Saúde do worker ocioso: TTL de 90 s (dequeue bloqueante até 75 s) para manter heartbeat
  dentro de 120 s, sem afrouxar a detecção de worker indisponível.

Referências primárias: [PostgreSQL FTS](https://www.postgresql.org/docs/17/textsearch-controls.html),
[pg_trgm](https://www.postgresql.org/docs/17/pgtrgm.html),
[OWASP CSV Injection](https://community.owasp.org/attacks/CSV_Injection).

## Base técnica

- Monorepo novo, sem copiar código ou dados de outros projetos.
- Python 3.13, FastAPI/Pydantic, SQLAlchemy 2, Alembic; PostgreSQL 17.
- React 19, TypeScript estável instalado, Vite e Tailwind v4.
- Dependências exatas registradas nos lockfiles após validação local.
- TypeScript 6.0.3 mantido: 7.0.2 não é compatível com o peer de typescript-eslint
  8.72.2. Sem forçar a resolução. Vitest 5.1.0 e ESLint 10.15.0 validados.
- Override minimatch `^11.0.1` limitado ao typescript-estree corrige advisory
  GHSA-g3hv-75wg-m249; lint, testes e build foram executados depois.
- Banco SQLite apenas para testes rápidos; Compose é a referência PostgreSQL.
- Identidade da instalação em migração inicial singleton, independente de hostname.
- Community é padrão; cadastro público Cloud depende de `ALLOW_ORG_SIGNUP`, desligado por padrão.
- Tokens oficiais preservados; extensões limitadas a zinc e feedback acessível.

## Decisões de produto

Ver [visão](VISAO.md) e [estado real](../STATUS.md); objetivos futuros não comprovam implementação.

## Licenciamento aprovado pelo titular

- GNU AGPL versão 3 somente, identificador `AGPL-3.0-only`, escolhida explicitamente
  pelo titular para o código próprio. Não foi concedida a opção de versões futuras.
- Texto oficial baixado de `https://www.gnu.org/licenses/agpl-3.0.txt`, sem edição.
- Instalações próprias, contribuições e hospedagem comercial seguem a mesma
  licença. Não foi estabelecida licença comercial alternativa.
- Inventário e condições de terceiros em [LICENCAS.md](LICENCAS.md).

## Identidade e isolamento

- PostgreSQL obrigatório para operações autenticadas; SQLite preservado apenas
  para testes rápidos das rotas de instalação.
- Conta runtime separada e RLS com FORCE; contexto transacional e repositório
  único. Migração aditiva, sem exclusão de volumes ou dados existentes.
- Sessões opacas em cookies HttpOnly/Secure em produção/SameSite Strict;
  CSRF com grant persistente vinculado à sessão. Sem JWT/localStorage na web.
- Argon2id via argon2-cffi; dependências e licenças incluídas nos inventários.
- Rate limit persistente por IP/conta e bloqueio progressivo sem depender de Redis.
- Community: só bootstrap explícito de uma empresa. Cloud: cadastro público
  somente com ALLOW_ORG_SIGNUP, padrão desligado. Seed de duas empresas só em
  Cloud não produtivo; idempotente e sem redefinir credenciais existentes.
- Identidades compartilhadas não têm senha global redefinida por admin de uma
  só empresa. Convites para contas existentes exigem a senha atual do titular.
- Todos os membros ativos acessam todos os clientes da sua organização;
  somente admin administra equipe/configurações. Gestor consulta equipe/auditoria.
- Busca ignorando acentos/caixa com unaccent e pg_trgm; nomes únicos por empresa,
  apelidos não únicos, paginação offset estável por criação/UUID.
- Decisão histórica substituída pela descontinuação nativa: interface web única; API e isolamento preservados.

## Registros e operação

- Finalizações são conferidas e confirmadas exclusivamente pelo autor, em tela
  ou lote atômico. Não existe aprovação do gestor nem confirmação automática.
- Pendência acima de 24 h recebe destaque visual; não é SLA obrigatório, ranking
  ou avaliação do técnico. Só confirmados contam no histórico oficial.
- Chamados abrem diretamente, inclusive urgentes; conhecimento é rascunho até revisão editorial.
- Conteúdo original/recebimento imutáveis; texto humano editado/versionado antes
  de confirmar. Horários distintos, UTC no banco e IANA na interface. Hora local
  ambígua/inexistente exige offset explícito, sem escolher silenciosamente.
- Um registro tem um destino; Derivar cria outro rascunho com origem e mesmo
  horário do fato. Não transforma nem apaga o original.
- Idempotência opcional para criação/derivação, obrigatória no fluxo da UI;
  escopo por organização/usuário/operação, chave em hash e lock transacional.
- Técnico vê chamados próprios, atribuídos ou em que participa; gestão vê a fila
  da empresa. Responsável/gestão opera, solicitante/gestão encerra. Resolver e
  encerrar são ações separadas; reabertura mantém o ticket e o histórico.
- Notificações internas por destinatário, polling de 15 s; sem serviço externo.
- Sem novas tecnologias/dependências; AGPL e inventários anteriores preservados.

## Mídia e processamento

- Redis 8/RQ, worker e dispatcher separados. Recibo durável no PostgreSQL antes
  de 202; HTTP não aguarda transcrição. Lease/locks evitam aplicação duplicada,
  fila urgente primeiro, 3 tentativas e timeout recuperável, sempre com digitação.
- ffmpeg apenas no worker; formatos reais normalizados para WAV mono 16 kHz.
  API valida bytes/tipo; duração e decodificação terminam assincronamente.
- Mock offline não inventa transcrição: reaproveita texto humano informado e
  marca simulação/incerteza. Áudio sem texto exige digitação manual no mock.
  faster-whisper opcional CPU/int8, modelo local, sem download de pesos no setup.
- **Benchmark de faster-whisper pendente**: medir memória de pico, CPU, tempo de
  carga, tempo total/fator em relação à duração e precisão em português por modelo
  e equipamento. Não houve inferência com pesos nem garantia de velocidade.
  Imagem/SDK e recusa offline de modelo ausente foram verificados.
- Storage local privado padrão; boto3 para S3 compatível. Imagem MinIO tentada
  retornou 401; perfil usa RustFS Apache-2.0 fixado por digest, testado com objeto
  fictício real (put/get/delete). Nenhuma fonte de terceiros foi copiada.
- Downloads assinados por arquivo/empresa/usuário/sessão, padrão 120 s; cookie
  continua obrigatório. Logs não registram query/URL nem conteúdo de áudio/texto.
- Retenção padrão manter. Só política explícita ou descarte pelo autor remove
  objeto; auditoria/metadados/texto ficam. Bucket S3 sem versionamento neste fluxo;
  backups, versões e replicação exigem política própria de remoção.
- Versão de template fixada inclusive para relato textual. Reprocessamento usa
  nova versão/snapshot e mantém histórico anterior. `rules` só aceita marcadores;
  contrato para `llm` futuro exige trechos literais, nenhum cliente LLM implementado.
- Ditado Web Speech desligado por empresa e opt-in por pessoa, com aviso prévio
  sobre fabricante; não funciona em paralelo com gravador. Texto ao vivo separado
  da transcrição e revisão; teste real de serviço do fabricante não foi realizado.
- Chamado urgente pode ser resolvido antes do áudio; transcrição posterior é
  comentário identificado, sem resolver/reabrir nem alterar fato/recebimento.
- Licenças novas e opcionais em [LICENCAS](LICENCAS.md). AGPL original preservada.

## Referências técnicas

- [RQ: workers](https://python-rq.org/docs/workers/) e [exceções](https://python-rq.org/docs/exceptions/).
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper).
- [Microfone e contexto seguro](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia).
- [SpeechRecognition e compatibilidade/privacidade](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition).
- [RustFS em contêiner](https://docs.rustfs.com/en/installation/container).

## Referências da arquitetura

- https://fastapi.tiangolo.com/tutorial/testing/
- https://alembic.sqlalchemy.org/en/latest/tutorial.html
- https://docs.sqlalchemy.org/en/20/
- https://vite.dev/guide/
- https://tailwindcss.com/docs/installation/using-vite
- https://docs.docker.com/compose/how-tos/startup-order/
- https://docs.docker.com/desktop/setup/install/windows-install/

Versões exatas estão nos locks; testes reproduzíveis em [TESTE_LOCAL](../TESTE_LOCAL.md).
## Compatibilidade de sessão por token

Token opaco curto e refresh rotativo preservados; hashes em banco com RLS
por usuário/empresa. Replay concorrente revoga a família, sem estender o prazo
absoluto. Cookie/CSRF web e bearer são fluxos separados. [Contrato](API_SESSAO_TOKEN.md).

## Descontinuação do cliente nativo — 16/11/2026

A interface suportada passa a ser a web responsiva. Cliente nativo,
pipeline e QR de abertura do aplicativo foram retirados. A interface suportada
é web; não há instrução de instalação nativa.
Migração 0006a, modelos e rotas bearer, RLS e testes de segurança foram
preservados para não quebrar contratos/dados existentes. Não houve
downgrade nem alteração de banco, redesign ou implementação de PWA.
