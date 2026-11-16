# Roteiro funcional com dados fictícios

## Identidade, clientes e permissões

Com Docker disponível, na raiz, PowerShell e Bash:

```text
docker compose --profile test run --build --rm tests
```

O perfil usa banco isolado `soldesk_test`, em tmpfs e sem porta no host. Não limpa
o banco da aplicação. Os testes criam identificadores próprios, não dependem de
senhas fixas e recusam executar a suíte de negócio em outro nome de banco.
Sem esse perfil, os testes PostgreSQL ficam explicitamente como ignorados;
uma execução SQLite não aprova o aceite de isolamento.

Roteiro manual com dados inventados:

1. No Community, faça bootstrap; ou no Cloud, execute o seed idempotente.
2. Entre como administrador, cadastre cliente e uma referência externa fictícia.
3. Pesquise nome/apelido com e sem acento, consulte e edite, marque inativo.
4. Em Equipe, crie um convite e copie o link. Aceite em outro perfil de navegador;
   repita o aceite para observar a recusa por uso único.
5. Crie integrante com senha temporária, copie uma vez e entre em outro perfil:
   acesso aos clientes só deve ocorrer após alterar a senha.
6. Entre como técnico: equipe administrativa não aparece e promoção direta é
   recusada. Desative esse membro como admin; a sessão perde acesso imediato.
7. Não é possível rebaixar/desativar o último admin. Tente mudar o fuso IANA da
   organização e confira o horário de cadastro no detalhe do cliente.
8. Na outra empresa, UUID/nomes de clientes da primeira não são acessíveis.
9. Use "Sair de todos os dispositivos" e confira o encerramento em outro perfil.

E2E autenticado: defina `E2E_ADMIN_EMAIL` e `E2E_ADMIN_PASSWORD` **somente no
ambiente**, com uma conta fictícia, e `PLAYWRIGHT_BASE_URL=http://127.0.0.1:8080`.
No PowerShell defina também `PLAYWRIGHT_CHANNEL=msedge` para o Edge instalado.
Em `web`, execute `npx playwright test --config playwright.identity.config.ts`.
No Bash use as mesmas variáveis com `export`; Chromium precisa ser instalado
com `npx playwright install chromium`. O teste não grava traces autenticados.
As credenciais não são argumentos de linha de comando nem arquivos versionados.

## Registros e chamados

Prepare a instalação fictícia conforme [testes](../TESTE_LOCAL.md); não apague volumes.

Use exclusivamente organização, contas e relatos fictícios:

1. Em **Atendimentos → Novo registro**, escolha cliente e finalização. Informe
   texto e fato retroativo. Antes de confirmar, o histórico padrão deve contar
   zero; a opção de provisórios mostra o item identificado como não confirmado.
2. Confira/edite o texto e confirme como autor. O horário do fato e recebimento
   devem permanecer, com revisão separada. Outro administrador não pode confirmar.
3. Crie duas finalizações e confirme pela fila **Minhas revisões**, em lote.
4. Derive uma finalização para conhecimento/chamado: deve surgir outro rascunho
   com o mesmo fato. Conhecimento enviado continua artigo rascunho, sem publicar.
5. Abra chamado normal/urgente: encaminhamento imediato. Solicite esclarecimento,
   responda, mencione integrante, transfira e mude prioridade. Os textos anteriores
   e intervalos de entrada/saída em espera devem continuar consultáveis.
6. Resolva, depois encerre e reabra. Mesmo código/ID, contador incrementado;
   não deve encerrar automaticamente ao resolver.
7. Consulte notificações e marque leitura. Outra pessoa/empresa não acessa o UUID.
8. Duas abas editando a mesma revisão devem produzir 409 na segunda escrita.
   Repetir criação com a mesma Idempotency-Key e corpo não duplica; corpo distinto
   com a mesma chave produz 409. Esses casos também são automatizados no pytest.
9. Em horário local ambíguo/inexistente por horário de verão, informe o ISO com
   offset explícito. Editar só texto não pode truncar os segundos do fato.

Regressão de persistência: `scripts/test-compose.ps1` executa migrações duas
vezes e reinicia banco/API sem apagar dados. Transições:
[docs/ESTADOS.md](ESTADOS.md); contratos e limites:
[docs/API_ATENDIMENTOS.md](API_ATENDIMENTOS.md). Resultado executado:
[STATUS.md](../STATUS.md).

## Áudio e anexos — mock offline

Repita o setup: gera também chave aleatória de downloads, migra até 0004 sem
apagar dados e inicia Redis/dispatcher/worker. Mantenha `TRANSCRIPTION_PROVIDER=mock`
e `STORAGE_BACKEND=local`. Basta Docker/Git/navegador para o uso web básico.
Redis e arquivos ficam em volumes privados; nenhuma porta de Redis/S3 é publicada.

1. Entre em **Atendimentos**, selecione cliente e destino. Informe texto fictício,
   opcionalmente com `Problema: ... Resultado: ...`; grave ou escolha áudio.
2. No computador use `http://localhost:8080` ou `127.0.0.1`. Autorize o microfone
   explicitamente, confira contador, pare, ouça a prévia, descarte/regrave e envie.
   Microfone recusado/indisponível mantém digitação/upload. Em celular físico,
   `http://IP-da-LAN` não é contexto seguro: use HTTPS de desenvolvimento com
   certificado confiável e configuração de proxy/origem; mantenha a opção de digitar.
   O setup não expõe a instalação à LAN nem instala certificado automaticamente.
3. Upload retorna sem esperar o worker. **Mock não reconhece fala**: reutiliza
   somente o relato digitado e sinaliza simulação/incerteza. Áudio sem relato real
   exige digitação antes de confirmar. Nenhum texto de sucesso/transcrição é inventado.
4. Confira texto bruto/organizado, alertas de possível credencial e trechos incertos;
   edite e confirme explicitamente. Fato/recebimento permanecem; processamento e
   revisão têm tempos separados. Conhecimento continua rascunho.
5. Como admin em **Configurar processamento**, edite rótulos/marcadores de templates
   e glossário (palavras sem números). Nova versão não altera registros anteriores.
   O texto livre sem marcadores é preservado; nada de diagnóstico inferido.
6. Anexe PDF/PNG/JPEG/TXT fictício no chamado ou histórico por cliente. Prepare
   acesso: URL exige a mesma sessão e expira em 120 s; outra empresa não tem acesso.
7. Em ambiente fictício, `docker compose stop worker`; crie chamado urgente com
   áudio, atribua/resolva manualmente. `docker compose up -d --wait worker` retoma
   o job; transcrição posterior é comentário e não reabre o chamado. Sempre retome
   o worker no fim do teste. Reprocessar/descarte ficam disponíveis conforme estado.
8. Retenção padrão mantém arquivos. Somente selecione remoção após confirmação
   ou N dias quando desejar essa política. Limpeza preserva metadados/auditoria.

Saúde autenticada em `/api/v1/media/health` e no painel de configuração. No host:
`docker compose exec worker python -m app.media_worker health`. Para operação
somente textual, pare worker/worker-whisper, ajuste `TRANSCRIPTION_PROVIDER=disabled`
e repita setup; upload de áudio informa indisponibilidade, texto/chamados funcionam.
Ao alternar provedor, pare explicitamente o worker antigo antes do novo setup;
os dois workers não devem consumir as mesmas filas com provedores diferentes.


Roteiro manual somente com dados fictícios:

1. Técnico prepara artigo de registro, preenche título/problema/procedimento,
   categoria/sistema e causa somente se relatada. Envia para revisão; não aparece
   na busca pública. Revisor devolve com motivo; autor corrige e reenvia.
2. Outro gestor/admin confere avisos e conteúdo; ambos os checkboxes são
   necessários. Publica, consulta diferenças e abre a origem: fato/envio preservados.
3. Busque `0x80070005`, `impressão`/`impressao` e `CFOP 5102`. Restrinja outro
   artigo a cliente A: só entra com esse filtro, nunca em sugestões do B. Arquive
   com motivo e confira busca explícita de arquivados.
4. Em Relatórios, consulte hoje/semana/mês/início e livre; filtre cliente/pessoa/
   equipe/categoria/sistema. Confira fatos no fuso da organização e comparação.
   Finalização pendente não soma em confirmadas. A abre e B resolve: atores distintos.
5. Resolva/encerre/reabra o mesmo Ticket: ações separadas e ticket único. Adicione
   espera por esclarecimento: bruto/líquido, mediana/P90/n e aviso de amostra pequena.
6. Técnico só vê si mesmo, inclusive exportando. Fórmulas de cliente/nome fictício
   recebem apóstrofo no CSV; auditoria registra exportação sem texto de relato.
7. Crie equipe como admin, veja composição atual e filtre. Pessoas começam em
   ordem alfabética; não há classificação de competência. Gráfico tem rótulos e
   tabela alternativa; confira largura móvel e temas. Sem dados há vazio explícito.
8. Mude nome/fuso em Configurações e confira que políticas de áudio/conhecimento
   continuam configuradas. Não use dados reais nestes testes.

Definições: [METRICAS](METRICAS.md). API: [conhecimento e relatórios](API_CONHECIMENTO_RELATORIOS.md).
Limites e resultados observados: [STATUS](../STATUS.md).
