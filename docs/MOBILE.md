# Acesso pelo navegador móvel

SolDesk Web responsivo; Android/iOS nativos descontinuados. Use a mesma
interface e URL da instalação em computadores e celulares. Acesso remoto
exige HTTPS; localhost é somente desenvolvimento.

Digitação permanece disponível. Microfone exige permissão explícita e
compatibilidade do navegador, com prévia antes do envio. O mock não reconhece fala.
Não há app distribuído, instalação por QR, PWA ou garantia de operação offline.

A API conserva o [contrato legado de sessão por token](API_FASE_06A.md),
sem dependência de SDK. [Validação nativa histórica](VALIDACAO_PROMPT_06A.md)
não comprova funcionamento atual em dispositivo físico.
