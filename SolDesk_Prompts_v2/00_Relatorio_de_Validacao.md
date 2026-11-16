# SolDesk — Relatório de validação dos prompts (v1 → v2)

**Veredito:** os 6 prompts originais eram bons na estrutura (fases em ordem, "não avance", honestidade de testes, dados fictícios, isolamento entre empresas). Havia, porém, **inconsistências entre prompts, lacunas em relação ao PDF e alguns riscos técnicos**. Tudo abaixo foi corrigido nos arquivos v2.

## 1. Inconsistências corrigidas

| Problema | Correção |
|---|---|
| Prompt 02 usava `organization_id`; o 03 usava `tenant_id` | Padronizado em `organization_id` |
| Estados do registro no 03 (`aprovado`, `publicado`) não batiam com o PDF (`confirmado`) | Finalização termina em `confirmado`, conhecimento em `publicado`; tabela de transições em `docs/ESTADOS.md` |
| Estados do chamado no 03 (`em_analise`, `em_validacao`) divergiam do PDF; faltava "aguardando terceiros" | Alinhado ao PDF: `aberto, em_andamento, aguardando_esclarecimento, aguardando_terceiros, resolvido, encerrado, reaberto` |
| 05 listava "assuntos que **demandam treinamento**", contradizendo a regra de não julgar | Item removido; só "assuntos recorrentes/mais frequentes" |
| 05 usava o nome "Matheus" como exemplo (pode ser pessoa real) | Trocado por "Técnico A" |
| 05 filtrava "por empresa" (ambíguo: organização ou cliente) | "Cliente atendido" |
| 01 pedia "dados fictícios" no setup antes de existir qualquer modelo; e pedia ID persistente de instalação sem tabela | Seed só a partir do 02; migração inicial cria só a tabela `installation` |
| `DECISOES.md`/`ROADMAP.md` só apareciam no 06 | Criados já no 01 |

## 2. Lacunas em relação ao PDF

- **Anexos de chamado/cliente** (PDF §07) nunca eram implementados, mas o 04 testava isolamento de "anexos". Agora há `Attachment` + upload no 04.
- **Armazenamento S3/MinIO, URLs temporárias, trilha de acesso, antivírus** (PDF §09 e §11): abstração `StorageBackend` (volume local + MinIO), URL assinada curta, auditoria de acesso, gancho de ClamAV.
- **Glossário técnico** (Firebird, CFOP, Sintegra, SGBR): agora tem cadastro e uso no provedor, só normaliza grafia, nunca números.
- **Menções e notificações** (PDF §07): `Notification` in-app criada no 03 (o 04 já dependia dela sem existir).
- **Pausas no tempo de resolução** (PDF §10): eventos de entrada/saída de espera guardados no 03; cálculo no 05 com mediana, P90 e `n`.
- **Quem revisa e o que fazer com pendências** (PDF §14, decisão em aberto): padrão definido (autor revisa; política configurável; nunca confirma sozinho; pendências envelhecem na fila).
- **Fuso da organização** era usado no 03 sem estar modelado: agora é campo da organização no 02.
- **Cadastro de empresa pelo site** (PDF §07) vs. modo Community: `SOLDESK_MODE` + `ALLOW_ORG_SIGNUP`.
- **Vínculos externos do cliente** (grupos, serviços): `ClientExternalRef` só armazenada.
- **Derivar um relato para outro destino** (ex.: finalização → artigo): ação "Derivar" com vínculo e `ocorrido_em` preservado.
- **LGPD** (PDF §11): rascunho `PRIVACIDADE_LGPD.md` no 06.

## 3. Riscos técnicos que os prompts originais não cobriam

1. **Contraste da paleta** (calculado): texto escuro funciona sobre dourado (9,6:1) e laranja (5,4:1); **falham** branco sobre dourado (2,1:1) e laranja (3,7:1), dourado como texto sobre creme (2,0:1) e laranja pequeno sobre creme (3,5:1). Regras e teste automático de contraste adicionados.
2. A paleta não tem verde/vermelho/azul: sem cores de estado, "erro" e "aviso" ficariam iguais. Permitida **apenas** uma extensão documentada de feedback, sempre com ícone e texto.
3. **Microfone no celular via `http://IP-da-LAN` não funciona** (exige HTTPS ou localhost). Isso quebraria o teste de áudio pelo navegador do celular; documentado e tratado.
4. **Web Speech API** no Chrome envia áudio a servidores do fabricante: aviso de privacidade e opt-in.
5. Formatos reais de áudio (webm no Chrome, mp4 no Safari/Expo) e ffmpeg no worker.
6. **RLS no PostgreSQL** falha silenciosamente se a API conectar como superusuário/dono das tabelas; orientação e teste adicionados.
7. Cookies de sessão sem **CSRF**; convites/redefinição de senha sem e-mail; proteção do último administrador.
8. Busca: texto completo tokeniza mal códigos de erro; busca sem acento/caixa ("mercearia" × "Merceária").
9. **CSV injection** na exportação; técnico vendo números de colegas; relatórios por pessoa ordenados como ranking.
10. Reenvios do celular duplicando registros: `Idempotency-Key`. Conflito de edição: `revision` + 409.
11. Credenciais ditadas em voz ("a senha é…") indo parar em artigos: alerta na revisão.
12. QR com esquema customizado: nunca conectar automaticamente; conferir `instance_id`.
13. Tailwind: a sintaxe `@theme` da paleta é do **v4**, agora explícito.

## 4. Mudanças de processo

- **`AGENTS.md` + `docs/REGRAS_DO_PROJETO.md`** criados no Prompt 01 com 10 regras permanentes; cada prompt seguinte manda ler esses arquivos. Evita deriva e funciona mesmo se trocar de chat.
- **Prompt 06 dividido em Parte A (mobile/QR) e Parte B (conectores, ponta a ponta, fechamento)**, com parada entre elas: era a fase mais pesada.
- Cenário ponta a ponta agora pede testes automatizados (pytest/Playwright) além do roteiro manual; revisão de segurança (`pip-audit`, `npm audit`, varredura de segredos) antes do relatório final.

## 5. Decisões (confirmadas pelo usuário, exceto a última)

- Revisão de finalização: **somente o autor** (sem revisão do gestor) — confirmado pelo usuário.
- Técnico vê só os próprios números; gestor/admin veem a equipe (confirmado).
- Todos os membros veem todos os clientes da organização (confirmado).
- Cadastro público de empresas desligado por padrão (confirmado).
- Artigo: gestor/admin publicam; autor não publica o próprio por padrão (opção da empresa) — **ainda não confirmado**.

## 6. Continua em aberto (do PDF §14, de propósito)

Nome definitivo, licença (Apache-2.0 × AGPL-3.0), escopo do MVP, benchmark do faster-whisper, prazos de revisão, SaaS e integrações prioritárias. Os prompts mandam registrar isso em `DECISOES.md` e **não** decidir sozinhos.
