# SOLDesk — PROMPT 03/06
## Registro único, três destinos, horários e regras de revisão

### PROMPT PARA O DESENVOLVEDOR

Continue no repositório do SolDesk após os Prompts 01 e 02. Leia `AGENTS.md`, `docs/REGRAS_DO_PROJETO.md`, `STATUS.md`, o código, as migrações e os testes antes de agir. Construa funcionalidades reais e verificáveis; nesta etapa, **somente entrada por texto** (áudio no Prompt 04).

**Regra de produto aprovada:** um relato gera um **registro** com um destino escolhido. **Finalização exige revisão antes de entrar no histórico confirmado; artigo exige revisão antes de publicar; chamado é encaminhado diretamente** e aceita comentários e pedidos de esclarecimento. Chamado urgente nunca espera IA ou aprovação.

#### Modelo e persistência (usar `organization_id`, como no Prompt 02)

1. `Record` (atendimento/relato): id, `organization_id`, `client_id`, `author_id`, `type` (`finalizacao` | `chamado` | `conhecimento`), `texto_original`, `texto_organizado` (opcional; nesta fase é o texto editado pelo usuário, e os templates automáticos chegam no Prompt 04), `status`, `revision`, referências opcionais ao ticket/artigo e a um registro de origem (`origem_record_id`).
2. **Campos temporais separados** (UTC no banco; exibição no fuso da organização): `ocorrido_em` (quando o fato aconteceu), `enviado_em` (recebido pelo servidor), `processado_em` (preenchido no Prompt 04), `revisado_em`, `revisado_por`, `publicado_em`. Nunca substituir o horário original pelo de revisão. A interface mostra, por exemplo, "Atendimento em 15/11 às 10h24 · Revisado em 15/11 às 17h51".
3. `ocorrido_em` vem sugerido como "agora", mas permite relato retroativo, **com registro em auditoria do valor original e do ajuste** e sem aceitar datas futuras. `enviado_em` é carimbo do servidor, imutável. Reservar `capturado_em` (horário informado pelo dispositivo, tratado como **não confiável**) distinto de `enviado_em`, para uso offline futuro.
4. **Estados do registro** (finalização e conhecimento): `rascunho` → `enviado` → `processando` → `aguardando_revisao` → `confirmado` (finalização) ou `publicado` (conhecimento), com `erro` e `cancelado` como estados laterais e devolução para correção a partir de `aguardando_revisao`. Entregar uma **tabela de transições permitidas** em `docs/ESTADOS.md`, validada no servidor. Nesta fase, sem áudio/IA, `enviado` passa direto a `aguardando_revisao`; `processando` só é usado a partir do Prompt 04. O estado `confirmado` corresponde ao "aprovado" falado nos documentos de produto; usar um só termo no código.
5. **Estados do chamado são independentes dos do registro.** Para registros do tipo `chamado`, o registro guarda apenas o ciclo de envio/erro; o ciclo de vida fica no `Ticket`.
6. **Histórico imutável de eventos** (reutilizar a infraestrutura de auditoria do Prompt 02): autor, mudança, data, valores relevantes; versionamento das edições do relato; **sem exclusão física** de registros revisados/confirmados (apenas `cancelado`/arquivado, com motivo).
7. **Concorrência e repetição:** edições usam o campo `revision` (conflito retorna 409 com mensagem clara). Criação de registros e chamados aceita o cabeçalho `Idempotency-Key` para que reenvios (rede ruim no celular) não dupliquem.
8. **Destinos a partir de outro registro:** um registro tem um único destino na criação, mas existe a ação "**Derivar**" (ex.: de uma finalização confirmada criar um rascunho de conhecimento ou um chamado), que cria um registro novo ligado ao de origem por `origem_record_id`, **preservando `ocorrido_em` do fato original** e sem alterar o original.

#### Política de revisão (decisão do produto)

- **A finalização é revisada somente pelo próprio autor** (conferir/corrigir e confirmar), em tempo real ou em lote no fim do expediente. **Não existe etapa de revisão do gestor para finalizações**, nem opção de configuração para isso nesta versão. Gestor e administrador não confirmam finalizações de outras pessoas. A revisão de **artigos** segue o Prompt 05. Registrar a decisão em `DECISOES.md` e `PERMISSOES.md`.
- Registros pendentes **nunca são confirmados automaticamente**. A fila mostra a idade da pendência e destaca as antigas; lembrete in-app opcional. Prazos rígidos ficam como decisão em aberto no `DECISOES.md`.
- Em relatórios e telas de gestão, provisórios aparecem sinalizados e **nunca como informação confirmada**.

#### Destino 1: finalização

- Técnico escolhe cliente e relata o procedimento/resolução; o envio cria o registro provisório em `aguardando_revisao`; ele aprova na hora ou deixa para a fila. Só após confirmar entra no histórico oficial do cliente (`confirmado`, com `revisado_em`).

#### Destino 2: chamado

- Ticket com código humano legível (sequência por organização, ex.: `SD-000123`), cliente, descrição, responsável, **prioridade (`baixa`, `normal`, `alta`, `urgente`)**, categoria, abertura, estado, comentários, **menções** (`@usuário`) e anexos previstos (upload real no Prompt 04).
- Estados: `aberto`, `em_andamento`, `aguardando_esclarecimento`, `aguardando_terceiros`, `resolvido`, `encerrado`, `reaberto`. Transições explícitas em `docs/ESTADOS.md`, cada uma registrando evento. Guardar o **instante de entrada e saída** de `aguardando_esclarecimento` e `aguardando_terceiros` (o Prompt 05 usa isso para descontar pausas).
- Separar **quem abriu**, **responsável atual**, **quem resolveu** e **quem encerrou**; resolver não encerra automaticamente. Reabertura incrementa `reopen_count` no mesmo ticket (não cria outro).
- Permitir resposta por texto, transferência de responsável, solicitação de esclarecimento, mudança de prioridade e encaminhamento imediato sem revisão formal.

#### Destino 3: artigo

- Cria somente **rascunho** de conhecimento ligado ao registro de origem; a tela de publicação e a base consultável vêm no Prompt 05. Rascunho jamais aparece como artigo aprovado.

#### Notificações in-app (necessárias já nesta fase e usadas no Prompt 04)

- Tabela `Notification` por usuário (tipo, referência, lida/não lida, data) para: chamado atribuído, menção, pedido de esclarecimento, resposta recebida e registro pronto para revisão. Consulta por polling simples com contador de não lidas; sem push remoto agora.

#### Interfaces

- Página **Novo registro** (cliente, tipo, texto, data/hora do ocorrido, responsável/prioridade/categoria condicionais ao tipo).
- **Minhas revisões** (com revisão em lote), **Histórico por cliente** (linha do tempo com autor, hora real do atendimento, hora da revisão e sinalização de provisórios), **Meus chamados**, **Fila de chamados** por estado, e tela de ticket com conversa cronológica e ação "Solicitar esclarecimento".
- Identidade visual pelos tokens de `docs/IDENTIDADE_SOL.md`. Estados de registros e chamados com **ícone e texto**, nunca só cor.

#### Testes de aceite

- Finalização enviada às 14:35 e revisada às 17:50: `ocorrido_em` e `enviado_em` permanecem; `revisado_em` registra 17:50. Ajuste retroativo de `ocorrido_em` deixa trilha; data futura é rejeitada.
- Finalização sem confirmação não entra na contagem de históricos confirmados.
- Chamado normal e urgente são encaminhados sem etapa de aprovação.
- Transições inválidas são rejeitadas; resolver e encerrar são eventos distintos; reabrir mantém o mesmo ticket.
- Reenvio com a mesma `Idempotency-Key` não duplica; edição concorrente gera 409.
- Usuário de outra organização não acessa registro, ticket ou notificação por UUID.
- Alterações deixam trilha de auditoria; resposta a um esclarecimento não apaga o relato anterior; "Derivar" preserva `ocorrido_em` original.

Entregue implementação, testes executados, migrações, arquivos alterados e passos locais. Atualize `STATUS.md`, `ESTADOS.md`, `PERMISSOES.md` e `TESTE_LOCAL.md`. **Não avance para o Prompt 04 automaticamente.**
