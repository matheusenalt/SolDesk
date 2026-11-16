# Validação da Fase 06 — Parte A

> Registro histórico anterior à descontinuação do cliente nativo em
> 16/11/2026. Referências a aplicativo, Expo e aceite Android descrevem
> aquele estado; não são instruções de instalação ou pendências atuais.

Data: 16/11/2026. **Implementação em validação; aceite Android obrigatório pendente.**
Não declarar fase completa, pronta para produção ou teste iOS aprovado.
Parte B não iniciada e depende de confirmação posterior ao aceite da A.

## Implementado

- Expo 58, React Native 0.88, React 19 e TypeScript 6; strings pt-BR e paleta
  oficial gerada. Escolher servidor, verificar domínio/nome/protocolo/identidade,
  confirmar, entrar; Cloud desativado sem URL fixa.
- QR público pelo painel administrativo e parser compartilhado com o app;
  URL manual/leitura de câmera/deep link não autenticam nem fazem rede sozinhos.
  Troca de identidade/divergência exige aviso e confirmação. HTTPS em release;
  HTTP/localhost/loopback normalizado somente em desenvolvimento explícito.
- Acesso de 15 minutos, refresh rotativo com prazo absoluto de 30 dias, replay
  revoga família com lock; RLS por empresa e usuário, hashes em banco. Cookies web
  e CSRF preservados. SecureStore nativo e memória volátil na prévia web.
- Clientes, texto/áudio m4a, revisão própria, chamado urgente/conversa/resolução,
  busca de artigos publicados e polling de notificações. API de negócio existente.
  Reenvio manual estável/idempotente, sem fila offline completa ou IA embarcada.
- Migração aditiva 0006a aplicada ao PostgreSQL de teste e instalação Docker
  existente. Setup executado sem apagar dados ou volumes; serviços saudáveis.

## Execuções e resultado

| Execução | Resultado observado |
|---|---|
| `docker compose --profile test run --rm tests` | **72 passed**, 83,15 s; PostgreSQL/Redis/ffmpeg reais. Aviso upstream Starlette sobre httpx, sem falha. |
| Novos testes backend `tests/test_mobile.py` | 7 casos: limites bearer/cookie/CSRF, rotação/replay concorrente, expiração, logout, senha/vínculo, isolamento HTTP/RLS, texto idempotente e m4a real processado/revisado. Incluídos nos 72. |
| Web Playwright autenticado, Edge desktop/emulação móvel | **34 passed**, 4,4 min, sem skips. QR e regressões anteriores; worker parado/retomado de fato. |
| Web Playwright instalação, Edge desktop/emulação móvel | **4 passed**, 1,1 min. |
| Prévia Expo/Playwright com API e PostgreSQL reais | **2 passed**, 36 s na execução final. Confirmação antes do login, consulta, resposta de POST perdida e reenvio sem duplicar, revisão/confirmar, chamado/comentário/resolução, busca/leitura de artigo publicado, notificações e logout; QR malicioso e divergência de identidade. Somente transporte adaptado ao navegador. |
| Testes Node mobile | **32 passed**, sem falhas/skips, incluindo URL/QR, identidade, cofre indisponível, refresh concorrente, logout offline e reenvio. |
| TypeScript/ESLint/formatação/build web e mobile | Aprovados na execução final. Web: **6 Vitest**, TypeScript/Vite gerados; mobile: TypeScript, ESLint, Prettier e bundle Android/Hermes. |
| Expo Doctor | **20/20** na execução após correção do peer expo-asset; versões compatíveis. |
| Bundle Android Expo/Hermes | Exportado com sucesso. **Não é APK nem execução Android.** |
| Tokens de tema | 32 pares aprovados e fontes geradas em sincronia. |
| npm audit web/mobile | **Zero vulnerabilidades conhecidas**, execução final concluída, após overrides pontuais de minimatch no mobile. |
| Licenças | 52 Python, 301 web e 595 mobile; opções compatíveis revisadas, sem pacote npm sem licença declarada. Texto AGPL oficial preservado por SHA-256. |

## Problemas encontrados e corrigidos

- Chave do throttle de login mobile excedeu varchar(80), reproduzida em PostgreSQL.
  Login nativo agora compartilha o propósito/limite de login existente, sem relaxar schema.
- Mobile fetch recebia o objeto da sessão como `this`, impedindo rede no navegador;
  chamada sem vínculo corrigida e coberta por teste e fluxo real.
- Respostas de mutação de Ticket não incluem conversa. App recarrega o detalhe
  após comentário/resolução, mantendo revisão e campos do contrato real.
- Expo Doctor apontou expo-asset ausente como peer nativo de expo-audio: dependência
  e plugin acrescentados; nova execução passou 20 verificações.
- Auditoria inicial sinalizou minimatch transitivo. Overrides restritos para as
  duas dependências afetadas, sem force upgrade; auditoria posterior zerada.
- Regex de recusa de controles exige exceção ESLint explícita/local e justificada;
  validação é mantida. Erros de formatação corrigidos e verificações repetidas.

## Revisão e publicação

Origem conferida: https://github.com/matheusenalt/SolDesk.git, branch main.
Último commit publicado continua `e4fa8bb899ffbe788de62bef4bf98f289a645d18`
(documentação do aceite da fase 05). Nenhum commit/push da fase 06 realizado,
pois o aceite nativo obrigatório ainda não foi executado. Não há novo Actions remoto.
Inventários e lockfiles preservados; caches, .env, ferramentas e dependências ficam
ignorados. Lista de arquivos candidatos ao Git conferida sem os diretórios/arquivos
proibidos. Busca local por padrões de chaves privadas/AWS/GitHub/OpenAI não encontrou
esses segredos em arquivos não ignorados. Fontes/configuração/testes revisados;
somente dados fictícios e código desta implementação. Busca textual não substitui
auditoria independente, gitleaks ou o fechamento ampliado da Parte B.

## Pendências obrigatórias e limites

1. Executar Android real ou emulador: conexão por URL/QR via LAN, autenticação,
   consulta cliente/chamado, texto e áudio capturado no microfone, mudança de
   estado, revisão e SecureStore. Nenhum Android SDK/adb/emulador encontrado
   neste computador; aguardando definição/disponibilidade de aparelho.
2. Registrar aparelho/Android/Expo e resultados do roteiro nativo histórico (retirado).
   Câmera, microfone, certificados, redirecionamento no fetch nativo e cleartext
   não são aprovados por testes JS, bundle ou prévia web. iOS não testado.
3. Concluir revisão de arquivos, commit no padrão da fase, push sem force e
   verificar Actions somente após aprovação de todos os testes obrigatórios.

Sem seleção multiempresa no app, push remoto, fila offline completa, Cloud oficial,
editorial completo no mobile ou fila de conectores. Notificações da tela consultam
30 itens recentes. Não há teste com transcrição real; mock reaproveita texto humano.
Parte B (conectores, cenário completo e revisão final LGPD) não iniciada.
