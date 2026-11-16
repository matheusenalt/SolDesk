# Visão do produto

SolDesk é uma aplicação web independente e open source para registrar suporte
enquanto ele acontece, preservar pendências entre turnos e reutilizar conhecimento.
O código próprio usa GNU AGPL v3 somente. Instalação própria e eventual hospedagem
comercial seguem a licença existente; nenhuma integração empresarial é obrigatória.

## Princípios

- Uma interface React responsiva para computador e celular; apps nativos descontinuados.
- Salvar relato e áudio antes do processamento; digitação sempre disponível.
- Conteúdo gerado não inventa diagnóstico, procedimento, código fiscal ou resolução.
- Separar processamento de áudio, fidelidade do texto e situação operacional.
- Preservar versões, autoria, UTC e horário do fato; revisão não altera o fato original.
- Permissões verificadas por organização e por objeto no servidor.
- Relatórios descrevem fatos; ausência de atualização não prova ausência de trabalho.
- Núcleo sem GPU, modelo grande, serviço pago ou Nextcloud obrigatório.

## Experiência desejada e situação real

| Modalidade | Objetivo | Situação atual |
|---|---|---|
| Finalização | Registrar atendimento concluído, com cliente ou atividade interna | Existe com cliente obrigatório e confirmação do autor; atividade interna e validação independente são planejadas |
| Em andamento | Atendimento único com atualizações, responsável e próxima ação | Planejado; não equivale ao status de um chamado |
| Chamado | Solicitação com responsável, prioridade, atualizações e aceite | Existe; prazos, aceite configurável e filtro de inatividade precisam evoluir |
| Tarefa | Ação simples por pessoa/equipe, data e prioridade | Planejada; não deve exigir o fluxo de aprovação de chamado |
| Conhecimento | Procedimento revisado, versionado e pesquisável | Existe; confirmação técnica de vigência por versão é planejada |

O painel desejado destaca abrir atendimento e pesquisar. Listas de tarefas,
atendimentos contínuos, calendário interno, busca global e PWA ainda dependem de
implementação. A base atual não deve exibir essas modalidades como prontas.

## Critérios futuros de aceite

Medir o registro por áudio em menos de um minuto de interação; retomar atendimento
no dia seguinte sem perder versões; acompanhar chamado e aceitar/devolver solução;
concluir tarefa simples; encontrar código técnico com versão e confirmação visíveis;
usar fluxos no computador/celular; demonstrar permissões e restauração antes de dados reais.
Esses critérios são objetivos de produto, não resultados de testes já executados.

## Decisões pendentes

Logo oficial; regras de validação entre leitores e autor; aceite quando solicitante
e responsável coincidem; retenção/quotas; plataformas homologadas; origem/autorização
de importações. Nextcloud/CalDAV e sincronização externa devem continuar opcionais.
Ver [estado real](../STATUS.md), [evolução](ROADMAP.md) e [limitações](LIMITACOES.md).
