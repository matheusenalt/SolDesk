# SOLDesk — PROMPT 04/06
## Áudio, anexos, transcrição assíncrona e templates configuráveis

### PROMPT PARA O DESENVOLVEDOR

Continue no repositório SolDesk com autenticação, clientes, registros e tickets dos Prompts 01–03. Leia `AGENTS.md`, `docs/REGRAS_DO_PROJETO.md`, `STATUS.md` e o código real. Não remova funcionalidades nem altere estados sem migração e testes. **Objetivo:** o técnico grava, envia, continua trabalhando e volta quando o servidor preparar o texto. A IA **não** roda no celular nem é obrigatória.

#### Armazenamento de arquivos (áudio e anexos de chamado/cliente)

1. Criar uma abstração `StorageBackend` com duas implementações: **volume local privado** (padrão) e **S3 compatível/MinIO** (opcional, por variável de ambiente e perfil do Compose). Chaves de objeto opacas, incluindo a organização no caminho; nada servido como arquivo estático.
2. Entidade `Attachment` genérica (organização, dono: registro/ticket/cliente, tipo, tamanho, hash, enviado por, enviado em). Implementar **upload de anexos em chamados e histórico do cliente** (previstos no Prompt 03): limite de tamanho configurável, lista de tipos permitidos, verificação do conteúdo real (assinatura do arquivo, não só extensão/MIME), nome original guardado como metadado e nunca usado como caminho, e um **gancho opcional de antivírus** (ex.: ClamAV por perfil do Compose; desligado por padrão, documentado).
3. Acesso somente por API autenticada e autorizada por organização, com **URL temporária assinada de curta duração** para download/reprodução, e **trilha de acesso** (quem abriu qual arquivo e quando). Sem URL pública permanente.

#### Arquitetura do áudio

1. **Frontend web:** gravação com `MediaRecorder` quando disponível, permissão de microfone explícita, contador, prévia/regravação, cancelamento e envio. Manter a digitação funcionando sempre. **Atenção:** `getUserMedia` e a Web Speech API só funcionam em contexto seguro (HTTPS ou `localhost`); no celular, abrir `http://IP-da-LAN` **não permitirá gravar**. Detectar isso e mostrar mensagem clara; documentar o teste via `localhost` no computador e, para o celular, via HTTPS de desenvolvimento ou pelo app nativo (Prompt 06). Aplicar a identidade Sol nos botões de gravação, estados de processamento e telas de revisão.
2. **Backend:** upload autenticado atrelado a registro/organização; validar MIME, assinatura do arquivo, **duração e tamanho** (padrões configuráveis, ex.: até 10 min e 25 MB), nomes opacos, armazenamento privado. Aceitar formatos reais dos clientes: webm/opus e ogg (navegadores Chromium/Firefox), mp4/m4a/aac (Safari e Expo/iOS), wav e mp3. Nunca expor URL pública.
3. **Fila assíncrona:** Redis + worker simples (RQ ou Celery) em contêiner próprio; estados `aguardando`/`processando`/`concluido`/`erro`, retries limitados com backoff, idempotência, logs **sem conteúdo sensível**, mensagem amigável. **Nunca segurar a requisição HTTP esperando a transcrição.** Jobs de áudio de chamados `urgente` entram numa fila de prioridade. Botões "Reprocessar" e "Descartar áudio e digitar", e processamento de jobs "presos" por timeout.
4. **Preparação do áudio no worker:** normalizar com ffmpeg para o formato do provedor (ex.: WAV mono 16 kHz) e checar duração; ffmpeg fica na imagem do worker, não na da API.
5. **Provedor de transcrição:** interface `transcribe(audio, language, glossary) -> text + segmentos + metadados`. Entregar o provedor **mock determinístico** (funciona 100% offline, sem custo) e o **faster-whisper opcional**, ativado por variável de ambiente, nunca carregado no processo da API, com limites de CPU/RAM e perfil do Compose separado. Sem GPU obrigatória e sem baixar modelos por padrão.
6. **Salvar separadamente:** transcrição bruta, texto editado, provedor/modelo/versão, início/fim do processamento (`processado_em`), erro e **apontamentos de incerteza** (por segmento: confiança baixa do modelo; no mock, trechos marcados de forma determinística para testar a interface). A interface destaca trechos incertos e pede conferência. Não inventar valores fiscais nem corrigir códigos CFOP automaticamente.
7. **Glossário técnico por organização** (termos como Firebird, CFOP, Sintegra, SGBR, Cervantes): cadastro simples na interface e semente com termos de exemplo; usado como dica ao provedor (ex.: *initial prompt*/hotwords do faster-whisper) e, no pós-processamento, apenas para **normalizar grafia de termos conhecidos**, nunca números, valores ou códigos.
8. **Dados sensíveis na fala:** detectar de forma simples padrões como "senha", "password", "token", "chave" e IPs/URLs com credencial e **sinalizar na revisão** ("possível credencial no texto: confira antes de confirmar"); sem armazenar segredo em campo à parte nesta fase.
9. **Retenção de áudio configurável por organização** (ex.: apagar após confirmação, após N dias ou manter), com tarefa de limpeza testada e registrada em auditoria. Em desenvolvimento, apenas áudios fictícios. APIs/LLM externos são **opt-in**, e chaves jamais vão ao frontend.

#### Templates e organização

- Templates por tipo e por organização: Finalização (motivo, procedimento, resultado), Chamado (problema, diagnóstico inicial, pedido, prioridade), Conhecimento (título, problema, causa, procedimento, resultado). **Versionados**; cada rascunho guarda a versão usada.
- Sem segunda IA: mapeamento por **marcadores falados** ("Problema: … Diagnóstico: … Solução: … Resultado: …"). Se a fala for livre e sem marcadores confiáveis, preservar a descrição integral, **sem fingir extração inteligente**.
- Interface de organizador (`rules` | `llm`). Entregar só `rules`; preparar contrato JSON validado (schema) para um LLM futuro, **com verificação de fundamentação**: toda informação de saída (inclusive números, códigos e nomes) deve constar na transcrição, caso contrário é rejeitada ou marcada como não verificada. Nenhuma API paga é exigida.
- Edição manual antes da aprovação, preservando o original e registrando alterações.

#### Regras entre tipo e processamento

- **Finalização:** ao concluir a transcrição → `aguardando_revisao`; após confirmação → histórico confirmado.
- **Conhecimento:** ao concluir → rascunho em `aguardando_revisao`; nunca publica sozinho.
- **Chamado:** criado/encaminhado imediatamente com o conteúdo informado; se o áudio ainda processa, sinalizar e depois anexar a transcrição. **Falha de transcrição ou fila parada nunca impede abrir, atribuir e resolver um chamado urgente manualmente.**
- Notificar no painel (infraestrutura de `Notification` do Prompt 03) quando o registro estiver pronto; push mobile é fase posterior.
- A transcrição fica vinculada a `ocorrido_em` e `enviado_em` já salvos. Processamento/revisão horas depois **não os altera**; apenas `processado_em` e `revisado_em` são preenchidos.

#### Ditado em tempo real (opcional/progressivo)

Prototipar a Web Speech API como complemento **quando suportada**, com fallback para gravação/upload ou digitação. Não assumir comportamento igual entre navegadores nem prometer captura simultânea confiável com `MediaRecorder` sem testes reais. **Aviso de privacidade obrigatório e opt-in:** em alguns navegadores (ex.: Chrome) o reconhecimento envia o áudio a serviços do fabricante; a interface informa isso antes de ativar, e a organização pode desabilitar o recurso. O texto ao vivo e a transcrição final do servidor podem divergir: manter ambos até a confirmação.

#### Testes e aceites

- Subir toda a stack com worker no localhost; o app segue usável com a IA desativada. Setup com **modo rápido sem modelo** (mock) e instruções para habilitar o worker opcional, com checagem de saúde própria. Sem GPU, sem API paga, sem instalar Python/Node fora dos contêineres para o teste web básico.
- Upload de áudio de exemplo com retorno assíncrono (mock); formato inválido (inclusive arquivo com extensão trocada), arquivo grande, duração excessiva, timeout, retry e "worker parado".
- Revisão de finalização e de conhecimento; chamado urgente criado e resolvido **antes** do fim da transcrição.
- Teste cruzado organização A/B para áudio e anexos, incluindo URL assinada expirada e URL de outra organização.
- Sinalização de incertezas e de possível credencial aparece na revisão; glossário não altera números.
- Documentar como habilitar o faster-whisper separadamente, recursos a medir e como verificar consumo no servidor. **Não garantir velocidade sem benchmark** (registrar o benchmark como pendente em `DECISOES.md`).

Atualize `TESTE_LOCAL.md`, `ARQUITETURA.md`, `STATUS.md` e `DECISOES.md` com o que realmente foi executado; **pare ao concluir esta fase.**
