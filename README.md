# SolDesk

Plataforma independente de suporte com histórico, chamados e conhecimento.
**Fase atual: 05, conhecimento revisado, busca PostgreSQL e relatórios descritivos.**
Dados por organização, PostgreSQL com RLS e sessões web com CSRF. Use somente
dados fictícios enquanto as fases e a revisão de produção não estiverem concluídas.

## Instalação do zero

1. Instale Git e Docker com Compose. Windows 10/11: Docker Desktop com backend
   WSL 2, virtualização habilitada e requisitos atuais do fabricante atendidos.
   Linux: Docker Engine e plugin Compose. Tenha um navegador atualizado.
2. Abra esta pasta em um terminal. Não é preciso instalar Python, Node ou banco
   separadamente para usar a versão em contêineres.
3. Execute no PowerShell: `powershell -ExecutionPolicy Bypass -File scripts/setup.ps1`.
   No Linux: `bash scripts/setup.sh`.
4. Abra http://localhost:8080 e http://localhost:8000/docs.
5. Verifique http://localhost:8000/api/v1/health e
   http://localhost:8000/api/v1/server-info.
6. Crie explicitamente o primeiro administrador (Community, uma única empresa):

   ```text
   docker compose run --rm migrate python -m app.manage bootstrap --organization "Empresa fictícia" --slug empresa-ficticia --name "Administrador fictício" --email admin@example.test
   ```

   Informe uma senha de 12–128 caracteres quando solicitada. Não há senha fixa.
   Entre na área da organização em http://localhost:8080.

Os scripts copiam `.env.example` e geram senhas locais distintas para migração e
usuário restrito da API (`RUNTIME_PASSWORD`) e chave de assinatura de downloads.
Não imprimem esses segredos, não
criam credenciais de aplicação e não apagam volumes. Se já instalou a fase 01,
execute novamente o setup para acrescentar a credencial runtime e as migrações
aditivas 0002–0005, preservando a instalação. O modo rápido padrão inicia Redis,
dispatcher e worker mock, sem baixar modelo.
A instalação não depende de chave de IA, GPU nem serviço pago.

## Portas

| Serviço | Endereço padrão | Alteração |
|---|---|---|
| Web | http://localhost:8080 | `WEB_PORT` no `.env` |
| API/OpenAPI | http://localhost:8000/docs | `API_PORT` no `.env` |
| Vite (perfil dev) | http://localhost:5173 | `DEV_PORT` no `.env` |
| PostgreSQL | somente rede interna | sem porta publicada |
| Redis / armazenamento S3 opcional | somente rede interna | sem porta publicada |

Atualize também `CORS_ORIGINS` se trocar portas. Para desenvolvimento com reload:
`docker compose --profile dev up -d --build db migrate api-dev web-dev`.

Leia [TESTE_LOCAL.md](TESTE_LOCAL.md) para comandos manuais, desenvolvimento fora
do Docker e validações. [STATUS.md](STATUS.md) informa o que foi realmente testado;
[ARQUITETURA.md](ARQUITETURA.md) explica os limites da fase.

Para a demonstração com **duas empresas fictícias**, use uma instalação local de
teste, ajuste `SOLDESK_MODE=cloud` no `.env`, repita o setup e execute
`./scripts/seed-demo/run.ps1` ou `bash scripts/seed-demo/run.sh`. Guarde as senhas
aleatórias exibidas uma única vez. Repetir não sobrescreve senhas existentes.
`ALLOW_ORG_SIGNUP=false` é o padrão, inclusive em Cloud.

Permissões: [docs/PERMISSOES.md](docs/PERMISSOES.md). Contratos, limites e CSRF:
[docs/API_FASE_02.md](docs/API_FASE_02.md) e
[docs/API_FASE_03.md](docs/API_FASE_03.md). Em **Atendimentos**, envie texto para
finalização, chamado ou rascunho de conhecimento. Finalizações só entram no
histórico confirmado após conferência do próprio autor, individual ou em lote.
Chamados, inclusive urgentes, abrem diretamente e têm conversa, menções,
esclarecimentos, transferência, resolução/encerramento e reabertura separados.
Horários do fato e revisão são distintos; derive novos destinos preservando o
fato original. [Transições e tempos](docs/ESTADOS.md). Notificações internas usam
polling e leitura individual.

Na Fase 04, grave com permissão explícita do microfone em `localhost`/HTTPS ou
envie um arquivo de áudio; a digitação continua disponível. Há prévia, cancelamento,
fila, incertezas, avisos de possível credencial, revisão humana, reprocessamento e
descarte. O **mock padrão reutiliza o texto digitado e NÃO reconhece fala**.
O faster-whisper é opcional, offline com modelo instalado explicitamente no
servidor; reconhecimento real e desempenho ainda precisam de benchmark.
Chamados urgentes podem ser resolvidos com o worker parado; o resultado posterior
é acrescentado à conversa. Artigos derivados seguem o fluxo editorial da Fase 05.

Anexos de cliente/chamado usam armazenamento privado local ou S3 compatível,
links curtos vinculados à sessão e auditoria. Administradores configuram glossário,
templates versionados, retenção (padrão manter) e ditado opcional com aviso de
privacidade. [Contrato da Fase 04](docs/API_FASE_04.md),
[teste local e provedores opcionais](TESTE_LOCAL.md) e
[relatório de validação](docs/VALIDACAO_PROMPT_04.md).
Na **Base de Conhecimento**, prepare um artigo a partir de registro acessível,
preencha os campos com o conteúdo relatado e envie para revisão. Por padrão,
gestor/administrador diferente do autor publica após duas conferências humanas.
Autopublicação fica desligada; o administrador configura os papéis e essa opção
na política editorial. Há devolução comentada, diferenças de versões e arquivamento.
Busca em português sem acento combina texto completo, trigramas e código exato;
não retorna rascunhos/revisões. Artigos restritos exigem filtro do respectivo cliente
e não são sugeridos em chamados de outro cliente. Fonte mantém suas permissões.

Em **Relatórios**, consulte períodos no fuso da empresa, compare a janela anterior,
filtre cliente/pessoa/equipe/categoria/sistema e exporte CSV auditado. Técnico vê
somente seus números; gestão vê a organização. Ações e tickets únicos, resolução
e encerramento, finalizações confirmadas e pendentes ficam separados. Tempos têm
mediana, P90, amostra e pausas; pessoas começam em ordem alfabética, sem avaliação
automática. Leia [definições das métricas](docs/METRICAS.md),
[contratos da Fase 05](docs/API_FASE_05.md) e
[validação da Fase 05](docs/VALIDACAO_PROMPT_05.md).
Mobile, SMTP e conectores continuam planejados. Não avançar ao Prompt 06 sem instrução.

Os arquivos originais de requisitos estão em [SolDesk_Prompts_v2](SolDesk_Prompts_v2/).
## Licença

Copyright (C) 2026 contribuidores do SolDesk.

O código próprio do SolDesk é disponibilizado sob a **GNU Affero General Public
License, versão 3 somente** (`AGPL-3.0-only`), sem garantia. O texto oficial,
inalterado, está em [LICENSE](LICENSE).

São permitidas instalações próprias, modificações, contribuições e hospedagem
comercial, observadas as condições da licença. Versões modificadas que atendam
usuários pela rede devem oferecer a esses usuários o código-fonte correspondente,
conforme a seção 13. A oferta comercial não dispensa essas obrigações.

Dependências mantêm suas próprias licenças. Consulte a
[revisão de licenças](docs/LICENCAS.md) e [como contribuir](CONTRIBUTING.md).
