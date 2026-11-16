# Segurança e privacidade

## Controles existentes

Organização vem da sessão no servidor; IDs não autorizam acesso. Context.query/get,
FKs compostas e PostgreSQL RLS FORCE reforçam o isolamento. O runtime não pode ser
superusuário, BYPASSRLS nem dono das tabelas. Migração usa conexão separada.

Senha Argon2id; sessão web opaca em cookie HttpOnly/SameSite Strict/Secure em
produção; CSRF nas escritas. Tokens bearer legados são separados de cookies;
refresh de uso único tem lock e revogação por replay. Login tem limitadores
persistentes por conta/IP. Ver [identidade](API_IDENTIDADE.md) e [token](API_SESSAO_TOKEN.md).

Arquivos privados exigem permissão sobre o dono; assinatura temporária também
depende da mesma sessão, usuário e organização. Conteúdo/tipo/tamanho são checados;
worker decodifica áudio antes de liberar download. ClamAV é opcional, não garantia
de que anexos são seguros. Não servir volume/bucket como diretório público.

Erros RFC 7807 e logs HTTP não expõem corpo/query/credenciais. Isso não torna o
histórico anônimo: snapshots de RecordVersion/AuditEvent contêm conteúdo de relatos.
Definir acesso, retenção e exportação para todas as cópias e backups.
Conteúdo gerado exige revisão humana; relatório nunca classifica competência de pessoas.

## Antes de dados reais — pendente de homologação

- HTTPS/reverse proxy, CORS/origens, cookies, headers e política de rede em produção.
- Encaminhamento confiável de IP: Nginx atual não envia X-Forwarded-For; vários
  usuários podem compartilhar o limitador por IP. Não confiar em header arbitrário.
- Quotas por organização, limites globais/concorrência de uploads e proteção contra abuso.
- Expurgo de sessões/grants CSRF expirados; endpoint CSRF não tem limitador próprio identificado.
- Recuperação consistente de banco/mídia/segredos: [backup](BACKUP.md).
- Política de privacidade, retenção e exclusão também de auditoria e cópias externas.
- Avaliação independente, dependências/imagens e testes de carga em ambiente isolado.

Use apenas dados fictícios até homologação. Não há certificação de segurança ou
autorização de produção implícita nos testes locais. Segredos ficam em variáveis
ou arquivo privado ignorado; nunca em Git, frontend, dumps públicos ou logs.
Relatos potencialmente sensíveis exigem revisão humana; heurísticas não provam anonimização.
Ver [permissões](PERMISSOES.md), [limites](LIMITACOES.md) e [contribuição](../CONTRIBUTING.md).
