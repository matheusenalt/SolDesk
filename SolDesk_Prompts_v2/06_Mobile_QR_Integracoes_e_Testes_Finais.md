# SOLDesk — PROMPT 06/06
## Aplicativo mobile, conexão por QR Code, conectores e demonstração local

### PROMPT PARA O DESENVOLVEDOR

Continue no mesmo repositório SolDesk após os Prompts 01–05. Leia `AGENTS.md`, `docs/REGRAS_DO_PROJETO.md`, `STATUS.md` e veja o estado real do backend/web antes de criar recursos; não recrie o projeto. Esta fase é grande, então ela tem **duas partes com ponto de parada**: **Parte A** (mobile + QR) e **Parte B** (conectores, cenário ponta a ponta e fechamento). Conclua e teste a Parte A, relate o resultado e **só continue para a Parte B depois da confirmação do usuário**.

---

## PARTE A — Aplicativo mobile e conexão por servidor

#### Modelo de instalação e conexão

- **Cloud:** servidor oficial com URL fixa e várias empresas isoladas. **Ainda não existe**: na primeira tela, mostrar a opção "Usar Cloud" desativada ("em breve"), sem URL embutida.
- **Community:** a empresa hospeda a própria instância (VPS ou servidor físico). Um único app conecta a qualquer instalação compatível, via "Conectar a servidor próprio" (digitar URL ou ler QR Code).
- O QR **só** configura o endereço e um identificador não secreto. Nunca incluir senha, refresh token, credencial do servidor ou segredo permanente.
- O app valida a URL, o certificado HTTPS em produção, `/api/v1/server-info`, a versão compatível e o nome da instância; mostra o **domínio para confirmação antes do login**. Guarda o `instance_id` após a primeira conexão e **avisa se ele mudar** para a mesma URL. `localhost`/HTTP somente em builds e cenários de desenvolvimento explícitos, com aviso.
- Não criar serviço central de resolução de IDs. ID sozinho não alcança máquina atrás de NAT/firewall; instalação privada exige VPN ou publicação segura com HTTPS.

#### QR Code

Conteúdo de exemplo: `soldesk://connect?server=https%3A%2F%2Fsuporte.exemplo.com.br&instance=<instance_id>` (o parâmetro `instance` é opcional e não secreto; o app confere com `server-info`). Como esquemas customizados podem ser acionados por outros apps, o app **nunca conecta automaticamente**: sempre mostra o domínio e pede confirmação. O painel de administração gera o QR e permite copiar a URL, e avisa quando a URL gerada é de desenvolvimento (HTTP/IP local).

#### Aplicativo React Native + Expo

1. Navegação mínima: escolher servidor → login → clientes → novo registro → meus chamados → minhas revisões → artigo/busca. Tema claro/escuro com a **paleta oficial Sol**, como constantes de tema espelhadas da fonte única de tokens definida no Prompt 01 (zinc-50 `#fafafa`, zinc-200 `#e4e4e7`, zinc-950 `#09090b`, dourado `#f1a502`, laranja `#e45825`, creme `#fbf8f2`), respeitando as regras de contraste de `docs/IDENTIDADE_SOL.md` e o teste de contraste. Não inventar cores equivalentes.
2. API real. Sessão em armazenamento seguro do dispositivo (ex.: SecureStore) com token curto + refresh rotativo; logout e troca de servidor; nenhuma URL de empresa embutida no código.
3. Captura de áudio com permissão explícita, enviada ao backend como no Prompt 04 (formatos m4a/aac e variações do Android), seguindo para revisão depois. Ditado ao vivo do sistema só como recurso opcional/fallback, com o aviso de privacidade, sem empacotar modelo de IA no app.
4. Mostrar estados do registro com **ícone e texto**: enviado, em processamento, aguardando revisão, confirmado/publicado, erro. Finalização e conhecimento exigem revisão; tickets são encaminhados diretamente. Reenvio seguro usando `Idempotency-Key` quando a rede cair; tratar claramente "sem conexão" (sem fila offline completa nesta fase; apenas mensagem e novo envio manual, ou rascunho local simples se couber).
5. Teste inicial em Android com Expo; explicar como validar em celular real (Expo Go, quando os módulos usados forem compatíveis) ou emulador na mesma rede, e quando é necessário *development build* (módulos nativos, HTTP em claro no Android). iOS não pode ser declarado testado sem dispositivo/ambiente compatível.
6. Documentar que `localhost` no celular aponta para o próprio aparelho: a API deve ser alcançada pelo IP da LAN (liberar a porta no firewall do Windows/Linux) ou por túnel de desenvolvimento. Não expor HTTP inseguro em produção. Node.js LTS e ferramentas do Expo só para testar o mobile fora do Docker; celular físico preferido; Android Studio opcional.
7. Notificações in-app/locais primeiro (consulta periódica à `Notification` do Prompt 03). Push remoto fica para depois, pois instalações privadas exigem desenho cuidadoso de entrega.

#### Critérios da Parte A

Mobile conecta por URL digitada e por QR ao localhost via LAN, autentica, consulta cliente e chamado, cria um registro por texto e outro por áudio, e vê o estado mudar. Teste automatizado das regras de validação de URL/`server-info` e do parsing do QR (incluindo QR malicioso, com credenciais ou esquema inesperado). Atualize `STATUS.md` e `TESTE_LOCAL.md` e **pare**, aguardando confirmação.

---

## PARTE B — Conectores, cenário ponta a ponta e fechamento

#### Integrações externas: preparação sem dependência

Criar o contrato de adapter (`test_connection`, `create_ticket`, `add_note`, `get_status`; recebimento de webhook futuro com **assinatura HMAC** verificada), persistência da configuração por organização com **segredos criptografados em repouso** (chave vinda de variável de ambiente, nunca no repositório, e nunca devolvidos em texto pela API), logs de sincronização, idempotência e novas tentativas. Implementar **somente conector mock/local** e um exemplo documentado de como escrever um conector; não exigir credenciais nem integrar GLPI, Nextcloud, Zammad ou WhatsApp reais sem nova autorização (integrações de empregadores exigem permissão). O SolDesk funciona integralmente com conectores desligados.

#### Cenário ponta a ponta obrigatório

Automatize o que for possível (testes de API com pytest e fluxo web com Playwright ou equivalente, rodando no Compose) e entregue um roteiro manual para o que depende de aparelho físico:

1. Docker Compose no localhost com dados fictícios, um administrador e um técnico.
2. Cadastrar o cliente "Mercearia Ramos".
3. Registro por texto e outro por áudio de demonstração (provedor mock).
4. Finalização: verificar `ocorrido_em`, `enviado_em`, fila de revisão, `revisado_em`, aprovação e histórico confirmado.
5. Chamado para outro responsável: criar sem aprovação, comentar, solicitar esclarecimento, responder e resolver (e encerrar depois, como evento separado).
6. Derivar um rascunho de conhecimento, revisar, publicar e buscar por código/termo exato.
7. Relatórios diário/semanal/mensal, separando criados, resolvidos e confirmados.
8. QR com a URL de desenvolvimento alcançável pelo celular; conectar o mobile, autenticar e consultar cliente/chamado.
9. Falhas simuladas, com comandos documentados: parar o worker (`docker compose stop worker`) e abrir um chamado urgente; falha de upload; empresa A tentando ler dados da B (web e API).

#### Revisão de segurança e privacidade (antes do relatório final)

- Auditoria de dependências (`pip-audit`, `npm audit` ou equivalentes) e varredura de segredos no repositório (ex.: gitleaks), com resultados registrados em `STATUS.md`.
- Checklist: cabeçalhos de segurança, rate limit, CSRF, CORS, expiração de sessões, URLs assinadas, isolamento (HTTP e RLS), logs sem dado sensível, limites de upload.
- Criar `docs/PRIVACIDADE_LGPD.md` como **rascunho**, não parecer jurídico: inventário dos dados tratados (nome/contato de clientes, áudios, textos, logs), retenção, exclusão/exportação, responsabilidades (quem é controlador/operador em Community vs. Cloud) e itens a definir antes de operar com dados reais.

#### Fechamento e documentação

README em português com **checklist fechado de requisitos por sistema operacional** (Windows com Docker Desktop/WSL2, Linux com Docker Engine/Compose, Git, navegador; Node LTS/Expo só para o mobile), comando exato para subir, migrar, criar o usuário de demonstração, acessar web/API e rodar testes. Verificar e atualizar `setup.ps1` e `setup.sh` para um primeiro teste em máquina limpa, com checagem de pré-requisitos e sem apagar volumes. Incluir instruções para testar por Wi-Fi local e requisitos para VPS/HTTPS (proxy reverso, certificado, firewall, backup do volume do banco e dos arquivos). Atualizar `ARQUITETURA.md`, `STATUS.md`, `TESTE_LOCAL.md`, `docs/DECISOES.md` e `docs/ROADMAP.md`, mantendo em aberto as decisões que ainda não foram tomadas (nome, licença, escopo do MVP, comparação de transcrição, hospedagem, integrações prioritárias).

Entregar o relatório final **funciona agora / parcialmente implementado / planejado**, com evidência dos testes executados. **Não declarar pronto para produção** sem teste de segurança, backups, recuperação e revisão de privacidade. **Não publicar o repositório nem escolher a licença por conta própria.**
