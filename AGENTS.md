# Regras permanentes do SolDesk

1. **Isolamento entre empresas:** todo dado de negócio pertence a uma `organization_id`; o filtro vem do contexto autenticado no servidor, nunca de um ID enviado pelo cliente. Um ID (de empresa, cliente, ticket, arquivo) nunca é credencial.
2. **Honestidade de status:** nunca declarar teste aprovado sem tê-lo executado; nunca criar tela "de sucesso" com dados falsos; `STATUS.md` separa **funciona agora / parcial / planejado**. Se não conseguir executar comandos, dizer.
3. **Horários preservados:** o horário do fato (`ocorrido_em`) nunca é substituído pelo horário de revisão ou publicação. Tudo em UTC no banco, exibido no fuso da organização.
4. **A IA nunca inventa:** nenhum diagnóstico, procedimento, valor fiscal, código (CFOP etc.) ou conclusão que não conste do relato; trechos incertos são sinalizados; conteúdo gerado nunca é confirmado/publicado sem revisão humana.
5. **Relatórios descritivos:** o sistema mostra fatos, totais, períodos e filtros. Nunca ranqueia "melhor/pior" técnico nem sugere incompetência, treinamento, sanção ou contratação.
6. **Dados fictícios e segredos:** só dados de teste inventados; nenhuma credencial real em Git, logs ou frontend; nada copiado de empregadores ou de outros projetos (inclusive Painel GL). Segredos só via variáveis de ambiente.
7. **Nada destrutivo por padrão:** scripts e setup não apagam bancos/volumes (`docker compose down -v`, `DROP`, `rm -rf` de dados ficam fora do fluxo padrão).
8. **Fluxo de trabalho:** ao iniciar, ler `AGENTS.md`, `STATUS.md`, `ARQUITETURA.md` e o código real; ao terminar, atualizar a documentação com o que foi de fato executado e **parar**, sem avançar para a próxima fase.
9. **Idioma:** interface e documentação em português do Brasil. Identificadores de código seguem o glossário de `docs/GLOSSARIO.md` (entidades em inglês, campos temporais e valores de estado em português sem acento, como `ocorrido_em` e `aguardando_revisao`). Textos da interface em arquivo de strings centralizado, para permitir tradução futura.
10. **Erros de API:** formato padronizado (RFC 7807 `application/problem+json`) com mensagens amigáveis na UI e sem vazar detalhes internos.

A solicitação atual do usuário autoriza executar os prompts em sequência, com validação e relato a cada fase. Não pule validações nem marque pendências como aprovadas.
