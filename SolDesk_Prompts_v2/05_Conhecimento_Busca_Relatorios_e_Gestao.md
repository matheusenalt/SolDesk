# SOLDesk — PROMPT 05/06
## Base de conhecimento, pesquisa e relatórios gerenciais

### PROMPT PARA O DESENVOLVEDOR

Continue no repositório real do SolDesk após os Prompts 01–04. Leia `AGENTS.md`, `docs/REGRAS_DO_PROJETO.md`, `STATUS.md` e revise os testes. **Objetivo:** transformar registros em artigos confiáveis e permitir relatórios diários, semanais e mensais **sem deturpar o comportamento dos técnicos**.

#### Base de conhecimento

1. Artigos por organização, com categorias e sistemas (ex.: fiscal, banco de dados, impressoras, delivery, SGBR, Cervantes, Retaguarda). Cada artigo é **geral** ou **restrito a um cliente**. Artigo restrito a cliente aparece no cadastro desse cliente e em buscas filtradas por ele, e **não é sugerido** em chamados de outros clientes. A visibilidade segue `PERMISSOES.md`.
2. Campos: título, problema, contexto, causa confirmada ou "não informada", procedimento, resultado, palavras-chave, sistema, versão do template, autor, revisor, datas e vínculo com atendimento/ticket de origem (link navegável).
3. **Estados do artigo:** `rascunho` → `aguardando_revisao` → `publicado`, com `devolvido` (volta ao autor com comentário) e `arquivado` (solução obsoleta, some da busca padrão mas mantém histórico). Quem pode revisar/publicar é **configurável por organização**; padrão: gestor e administrador publicam, e a regra "o autor pode publicar o próprio artigo" fica desligada por padrão e é uma opção da empresa (registrar em `DECISOES.md`).
4. Versionamento de artigos com diferença entre versões e autor/data de cada mudança. Conteúdo gerado por IA nunca é publicado sem confirmação humana. Exibir aviso em campos incertos e em códigos fiscais não verificados, e o alerta de possível credencial no texto (Prompt 04) antes da publicação.
5. **Busca inicial com PostgreSQL**, sem serviço externo: texto completo em português com `unaccent` **combinado** com `pg_trgm`/correspondência exata para **códigos e mensagens de erro** (ex.: `0x80070005`, "CFOP 5102"), pois a busca textual por palavras tokeniza mal esses códigos. Filtros por categoria, sistema, cliente e período; índices adequados; resultados com trecho destacado e link para a fonte original. A busca de publicados **nunca retorna rascunhos nem artigos aguardando revisão**; rascunhos próprios e fila de revisão ficam em telas separadas. Busca semântica/pgvector é recurso futuro, não bloqueia o MVP.
6. Sugestão de artigos relacionados em tickets por coincidência de termos/categorias, rotulada como **sugestão, não diagnóstico**.
7. Registrar consultas a artigos como evento agregável (artigo, organização, data) para "artigos mais consultados", **sem expor ranking de leitura por pessoa**.

#### Relatórios e gestão

Dashboard com período livre e visões pré-configuradas **do dia, da semana, do mês e desde o início do uso**, com comparação entre períodos; filtros por **cliente atendido**, equipe, responsável, categoria e sistema (o isolamento por organização já é implícito). Tudo calculado dos eventos e registros reais, **no fuso da organização**, incluindo limites de dia/semana/mês.

Antes de codificar, escreva `docs/METRICAS.md` com a **definição de cada indicador**: fórmula, eventos de origem, o que entra e o que fica de fora, tratamento de pausas e fuso. Para tempos, mostrar **mediana e percentil 90 com o tamanho da amostra (n)**, e aviso quando n for pequeno, em vez de médias isoladas.

**Quem vê o quê:** gestor e administrador veem equipe e relatórios completos; técnico vê **apenas os próprios números**. Exportações respeitam o mesmo escopo.

**Indicadores separados — não misturar:**

- Atendimentos registrados no período; finalizações **confirmadas** vs. **aguardando revisão** (provisórias sinalizadas, nunca somadas às confirmadas).
- Chamados abertos, atribuídos, movimentados, resolvidos, encerrados, reabertos e aguardando terceiros. Um chamado pode passar por vários responsáveis; a autoria de cada ação é registrada.
- Tempo até primeira ação/resposta e tempo de resolução **descontando as pausas** `aguardando_esclarecimento` e `aguardando_terceiros` (e também o valor bruto, lado a lado), quando os eventos permitirem. Não inventar duração de atendimento se só houver horário de envio. Não há medida de "complexidade" no sistema: mostrar a distribuição por categoria/prioridade e deixar a interpretação à gestão.
- Por funcionário, separar o que **abriu**, **assumiu**, **comentou**, **encaminhou**, **resolveu** e **encerrou**; contar **ações** e **tickets únicos** separadamente, com distribuição por dia/semana/mês para não confundir volume de registro com solução efetiva.
- Agrupamento de assuntos/sistemas por funcionário e por equipe **apenas como dado consultável, sem atribuir causa**. Ex.: "Técnico A abriu 12 chamados do sistema fiscal neste mês".
- Clientes com maior número de atendimentos; problemas e assuntos **recorrentes/mais frequentes**; artigos mais consultados. (Não existe item "assuntos que demandam treinamento": isso é conclusão da gestão, não do sistema.)
- Fila atual: chamados por responsável, prioridade, idade, pendências e pedidos de esclarecimento.
- Carga de trabalho: registros, chamados simultâneos e pendências no tempo, como **sinal de investigação**, nunca prova de sobrecarga ou de necessidade de contratação.

#### Interpretação responsável

**Regra explícita:** "funcionário abriu muitos chamados" não implica falta de conhecimento. Pode indicar mais demanda, especialização, distribuição desigual, escalonamento adequado, complexidade maior ou classificação equivocada. **O software apenas apresenta fatos, totais, períodos e filtros**; a gestão interpreta e decide fora da automação. Em tabelas e gráficos por pessoa: **ordem alfabética por padrão** (a gestão pode reordenar manualmente por coluna), **sem numeração de posição, medalhas, "top/bottom", semáforos vermelho/verde ou metas automáticas**, e sem frases geradas do tipo "domina/não domina", "precisa de curso", "contratar". Incluir um texto fixo de contexto nas telas por pessoa explicando as possíveis razões acima.

#### Interface

- **Base de Conhecimento:** categorias, busca, rascunhos, fila de revisão, versões e artigo.
- **Relatórios:** cartões e gráficos simples, tabelas detalhadas e **exportação CSV** respeitando permissões, com proteção contra *CSV injection* (prefixar células que começam com `=`, `+`, `-`, `@`) e registro da exportação em auditoria.
- Tokens da paleta Sol de `docs/IDENTIDADE_SOL.md` em cartões, tabelas e gráficos (sem texto dourado/laranja pequeno sobre creme; texto escuro sobre dourado/laranja); cores de status acessíveis nos dois temas, **sempre com texto/ícone**. Gráficos com rótulos e tabela alternativa legível por leitor de tela.
- Histórico por cliente e por técnico, respeitando permissões.
- Estado vazio claro quando não há dados e aviso fixo: "estatísticas refletem apenas atendimentos registrados".

#### Testes

1. Artigo `aguardando_revisao`, `devolvido` ou `rascunho` não aparece na busca de publicados; `arquivado` só aparece com filtro explícito.
2. Organização A não acessa artigos, métricas nem exportações da B (HTTP e, onde existir, RLS).
3. Resolver e encerrar são eventos distintos, com contagens corretas.
4. Ticket reaberto conta como **um** ticket com reabertura, não como tickets novos.
5. Finalização pendente de revisão não soma nas finalizações confirmadas.
6. Dados fictícios em fusos diferentes e nos limiares de período (virada de dia, semana e mês; ex.: 23:30 no horário de São Paulo é outro dia em UTC).
7. Um técnico fictício abre vários tickets de um sistema: o dashboard mostra a contagem objetiva e **não** sugere deficiência, curso, contratação ou sanção; teste verifica ausência de ranking/posição e de texto avaliativo na API e na interface.
8. "Chamados criados por A" e "chamados resolvidos por B" aparecem separados, sem atribuir a resolução a A; filtros diário, semanal, mensal e acumulado conferem.
9. Tempo de resolução desconta pausas corretamente em cenário com `aguardando_esclarecimento`; mediana/P90 e `n` aparecem.
10. Técnico não vê números de colegas; exportação CSV neutraliza fórmulas e respeita o escopo.
11. Busca por código exato e por termo com/sem acento retorna o artigo publicado esperado; artigo restrito a cliente não é sugerido em ticket de outro cliente.

Entregue rotas, migrações, interface real, testes executados, exemplos de relatório e documentação atualizada (`METRICAS.md`, `STATUS.md`, `ARQUITETURA.md`). **Não avance para o Prompt 06 sem autorização.**
