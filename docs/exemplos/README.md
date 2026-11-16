# Exemplos de relatório — dados exclusivamente fictícios

[JSON](relatorio-ficticio.json) e [CSV](relatorio-ficticio.csv) obtidos da API local
real em 16/11/2026, em organização nova criada especificamente para o exemplo.
Não foram montados à mão como resposta de sucesso. Senha aleatória ficou somente
em memória/ambiente; não há sessão, token, e-mail ou credencial nos arquivos.
IDs identificam apenas entidades fictícias da instalação de teste e não dão acesso.

Dados: duas finalizações (uma confirmada, outra aguardando revisão) e um chamado
que abriu, resolveu, encerrou e reabriu mantendo o mesmo ID/código. As contagens
de confirmação, pendência, abertura e reabertura foram verificadas contra a resposta.
Tempos são os intervalos reais dessa automação, **não** duração de atendimento ou
referência de desempenho humano. A amostra é pequena e identificada como tal.

Filtro de cliente, período desde o início, fuso America/Sao_Paulo; horários do
servidor em UTC e fila atual no instante da geração. Consulte [METRICAS](../METRICAS.md)
para interpretar ações/tickets únicos, comparação, pausas e estados atuais.
CSV foi emitido por POST autenticado/CSRF e auditado; JSON e CSV são fotografias
de consultas consecutivas, então generated_at/idade da fila podem diferir ligeiramente.
