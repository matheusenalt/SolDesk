# SOLDesk — PROMPT 01/06
## Arquitetura do produto, regras permanentes e ambiente local executável

**Como usar:** copie todo o bloco "PROMPT PARA O DESENVOLVEDOR" para o chat/agente que desenvolverá o SolDesk. Envie os prompts 01 a 06 em ordem e só mande o seguinte depois de concluir e testar a etapa atual. Se o chat não tiver acesso ao repositório ou a arquivos locais, anexe o repositório ou autorize a criação do zero. Cada prompt posterior começa mandando ler o `AGENTS.md` criado aqui, então funciona mesmo se você trocar de chat entre as fases.

---

### PROMPT PARA O DESENVOLVEDOR

Atue como arquiteto de software, desenvolvedor full stack e revisor de segurança. Quero iniciar um projeto **pessoal, open source e independente**, com nome provisório **SolDesk**. Ele roda primeiro no localhost e, depois, em instalação própria (Community) e SaaS gerenciado (Cloud).

**Proposta funcional:** plataforma de suporte que transforma registros rápidos por voz ou texto em histórico do cliente, chamado e base de conhecimento. Um mesmo relato (entrada) escolhe um entre três destinos: (1) **finalização** no histórico de um cliente; (2) **chamado** com responsável; (3) **artigo** de conhecimento. Princípio central: *registrar precisa ser mais fácil do que deixar de registrar.* Áudio e IA entram por etapas; o núcleo não depende de Nextcloud, GLPI, WhatsApp ou qualquer serviço externo, e o sistema deve continuar útil sem nenhuma IA (digitação, regras e chamado manual são caminhos de primeira classe).

**Stack base sugerida:** backend Python + FastAPI + Pydantic + SQLAlchemy 2 + Alembic; PostgreSQL; frontend React + TypeScript + Vite + **Tailwind CSS v4** (a paleta abaixo usa a sintaxe `@theme` do v4); pytest, Vitest e Docker Compose. Linters/formatadores: ruff (Python) e ESLint + Prettier (web). Usar versões estáveis compatíveis, conferir comandos na documentação oficial e registrar as versões escolhidas em `docs/DECISOES.md`. Depois: worker de transcrição (Redis), React Native/Expo e conectores opcionais. Não criar microserviços desnecessários.

#### Regras permanentes do projeto (criar agora, valem para todas as fases)

Crie `AGENTS.md` na raiz (e, se a ferramenta usar, um `CLAUDE.md` apenas apontando para ele) e `docs/REGRAS_DO_PROJETO.md` com o texto abaixo. Todo prompt futuro mandará ler esses arquivos primeiro.

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

#### Identidade visual da família Sol — PALETA OFICIAL RECEBIDA

Usar os valores reais fornecidos pelo usuário a partir de `frontend/input.css` do projeto Sol Gestor MEI, preservando exatamente nomes e HEX:

    @theme {
      --color-zinc-50: #fafafa;
      --color-zinc-200: #e4e4e7;
      --color-zinc-950: #09090b;
      --color-sol-gold: #f1a502;
      --color-sol-orange: #e45825;
      --color-sol-cream: #fbf8f2;
      --spacing: 0.25rem;
      --radius-xl: 0.75rem;
    }

Criar `docs/IDENTIDADE_SOL.md` como fonte da verdade, com orientações de aplicação e **tokens semânticos** (primary, accent, surface, text, border, feedback) mapeados para as variáveis acima. Não substituir a paleta nem inventar HEX "parecidos". Regras:

- **Tema claro:** fundos creme; texto zinc-950; ações principais em dourado; laranja só como destaque pontual; superfícies/bordas em zinc-50/zinc-200.
- **Tema escuro:** base zinc-950 com os mesmos acentos Sol. Para superfícies intermediárias do escuro, usar a escala zinc padrão do Tailwind (ex.: zinc-900/800), documentando que não vêm da paleta recebida.
- **Contraste medido (WCAG), já calculado para esta paleta — respeitar:** zinc-950 sobre dourado 9,6:1 e sobre laranja 5,4:1 (**usar texto escuro nesses fundos**); texto zinc-950 sobre creme 18,8:1. **Falham:** branco sobre dourado (2,1:1), branco sobre laranja (3,7:1, abaixo de 4,5:1 para texto normal), dourado como texto sobre creme (2,0:1) e laranja como texto pequeno sobre creme (3,5:1). Dourado/laranja sobre creme servem apenas como preenchimento, ícone grande ou detalhe, nunca como texto corrente.
- **Cores de feedback:** a paleta não traz verde/vermelho/azul. Permitir **somente** os tokens de estado (sucesso, erro, aviso, informação) como extensão explícita do SolDesk, documentados em `IDENTIDADE_SOL.md` como "extensão — não vem da paleta Sol", com valores de contraste conferido nos dois temas. Todo estado deve ter **ícone e texto**, nunca só cor.
- Entregar um script/teste simples que calcule o contraste dos pares de tokens usados e falhe abaixo de 4,5:1 (texto) ou 3:1 (elementos de interface).
- Manter `--spacing` e `--radius-xl`. Centralizar os tokens num único arquivo-fonte (ex.: `packages/tokens/` ou `docs/tokens.json`) do qual o CSS da web é gerado/copiado e que o mobile espelha em constantes (o React Native não consome variáveis CSS).

#### Pré-requisitos para testar em uma máquina local

- Suportar Windows 10/11 com WSL 2 e Docker Desktop, e Linux com Docker Engine + plugin Compose. Informar condições mínimas de cada sistema, incluindo virtualização quando necessária.
- Exigir apenas **Git, Docker com Compose e um navegador** para testar a versão web conteinerizada. Python, Node.js e PostgreSQL separados não são obrigatórios nesse modo.
- VS Code é só editor opcional; informar espaço em disco e RAM a conferir, sem prometer desempenho antes de medir. Testes básicos funcionam sem GPU e sem baixar modelos de IA.
- Documentar as verificações de pré-instalação: `docker --version`, `docker compose version`, `git --version`; no Windows, como verificar o WSL 2.
- Preparar `scripts/setup.ps1` e `scripts/setup.sh` para: validar dependências, orientar a cópia de `.env.example` para `.env`, subir serviços e executar migrações. (Dados de demonstração só existirão a partir do Prompt 02; aqui o script deve deixar um ponto de extensão `scripts/seed-demo` vazio e documentado.) Scripts idempotentes, sem apagar banco/volumes e sem credenciais reais.
- Incluir alternativa manual equivalente (comandos explícitos em PowerShell e bash) para quando os scripts não puderem ser executados. Se o Docker não estiver configurado, falhar com orientação clara.

#### O que implementar nesta etapa

1. Inspecione os arquivos existentes antes de alterar algo. Se o repositório estiver vazio, crie um monorepo simples: `backend/`, `web/`, `mobile/` (apenas reservado, com README), `docs/`, `infra/`, `scripts/` e `tests/` onde adequado.
2. Docker Compose para subir banco, API e web. Perfil padrão para teste (web construída e servida) e perfil `dev` com hot reload. Não publicar o PostgreSQL em interfaces externas; se expuser porta para debug, restrita a `127.0.0.1`.
3. `.env.example` sem segredos reais; permitir rodar API e frontend também fora do Docker durante o desenvolvimento. Preparar já a variável `SOLDESK_MODE` (`community` | `cloud`), usada nas próximas fases.
4. `GET /api/v1/health` e `GET /api/v1/server-info`. O segundo retorna nome do produto, versão da API, **ID persistente da instalação**, modo e recursos suportados (`capabilities`), sem dados privados. Como o ID precisa persistir, a migração inicial cria **apenas** uma tabela mínima de instalação (ex.: `installation` com `instance_id` gerado uma vez); nenhum outro modelo de negócio ainda.
5. CORS estrito para desenvolvimento, logging estruturado básico, tratamento consistente de erros (RFC 7807) e OpenAPI.
6. Alembic configurado; migrações executáveis duas vezes sem erro indevido.
7. Tela inicial responsiva em pt-BR com a paleta Sol, componentes consistentes, navegação de exemplo e mensagem "backend conectado" baseada em chamada real à API. Nenhuma rota de negócio ainda.
8. Documentos: `ARQUITETURA.md` (decisões técnicas e diagrama navegador/API/banco/worker/mobile futuro; deixar explícito que o armazenamento de arquivos será uma abstração com volume local e S3/MinIO compatível, e a fila usará Redis, ambos nas próximas fases); `TESTE_LOCAL.md` (pré-requisitos, comandos Windows/Linux, portas e URLs, saída esperada, teste de API, falhas frequentes); `STATUS.md`; `docs/DECISOES.md` (registro de decisões, já listando como **em aberto**: nome/identidade, licença, escopo do MVP, comparação de transcrição, prazos/responsáveis de revisão, modelo de hospedagem, integrações prioritárias); `docs/ROADMAP.md` (as fases do produto: protótipo local, áudio funcional, operação básica, aplicativo mobile, produto ampliado); `docs/GLOSSARIO.md`; `CONTRIBUTING.md` e `LICENSE` provisórios dizendo "licença a definir" (**não escolher licença**).
9. CI mínimo opcional (ex.: GitHub Actions) rodando lint e testes, sem segredos.

#### Critérios de aceite

- `docker compose up --build` (ou equivalente documentado) sobe tudo; frontend e documentação da API abrem no navegador.
- Teste mínimo passo a passo documentado: subir contêineres, `docker compose ps`, `/api/v1/health`, abrir frontend, `/api/v1/server-info`. Portas exatas definidas no README gerado, com instrução de como trocá-las caso estejam ocupadas.
- Bootstrap local documentado; nenhuma integração externa, chave de API ou serviço pago exigido.
- Testes automatizados para health e server-info; `instance_id` permanece o mesmo após reiniciar os contêineres.
- Sem login fictício que pareça seguro; sem rotas de negócio abertas.
- Não instalar Whisper/Ollama nem consumir APIs pagas nesta fase. Sem dados de clientes reais.
- README com seção "Instalação do zero" para quem só tem Git e Docker.
- Demonstrar que o frontend usa os HEX recebidos, que `docs/IDENTIDADE_SOL.md` existe, e que o teste de contraste passa nos temas claro e escuro.

#### Forma de trabalhar

Implemente o código real, entregue lista de arquivos criados/alterados, comandos executados, resultados de testes e bloqueios. Não declare testes aprovados sem rodá-los. **Não avance para o Prompt 02.** Ao final, dê instruções para o usuário testar no localhost.

**IMPORTANTE:** o SolDesk deve ser novo, sem copiar código, base de dados, credenciais ou arquivos do Painel GL/empregador. A licença será escolhida separadamente antes da publicação pública (comparar AGPL-3.0 e Apache-2.0).
