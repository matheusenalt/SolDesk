# Backup, restauração e atualização

**Situação: planejamento operacional; restauração completa ainda não homologada.**
Volumes persistentes e reinício com UUID preservado não comprovam recuperação.
Não existe instalador Linux completo nem rotina automatizada de backup no projeto.

## Conjunto recuperável

- PostgreSQL completo: dados, histórico, versões, auditoria, instalação e revisão Alembic.
- Objetos privados no volume `media_data` ou bucket S3; preservar vínculo com o banco.
- Configuração/segredos do operador, chaves de assinatura, credenciais e política de acesso.
- Versão exata do código/imagens, extensões, migrações, checksums e procedimento de restauração.

Segredos nunca entram no Git nem em relatório público. Proteja cópias com controle
de acesso, criptografia e destino externo à máquina/conta de produção, conforme
política definida pelo operador. Logs e snapshots de auditoria podem conter relatos.
Retenção/exclusão deve considerar banco, mídia, versões do bucket e todas as cópias.

## Procedimento a homologar, sem tocar produção

1. Definir RPO/RTO, retenção, frequência, responsável e destino; hoje não homologados.
2. Obter snapshot consistente de banco e objetos, pausando escritas quando necessário;
   um dump isolado não demonstra consistência temporal com uploads concorrentes.
3. Conferir integridade, permissões e disponibilidade dos segredos de recuperação.
4. Restaurar em projeto Compose, rede e volumes NOVOS, com portas isoladas e sem
   conectores externos. Nunca usar o banco/volume original como destino do ensaio.
5. Recriar papéis de migração/runtime e permissões compatíveis; confirmar ausência
   de superusuário/BYPASSRLS/ownership no runtime, RLS FORCE e contexto por transação.
6. Verificar UUID da instalação, revisão Alembic, login, duas organizações fictícias,
   isolamento HTTP/SQL, histórico, artigos, anexos/áudios, hashes e retomada dos jobs.
7. Registrar tempo real de recuperação, dados recuperados e resultado; só então
   declarar RPO/RTO e restauração aprovados. Esta documentação não executa esse ensaio.

## Atualização e rollback

Fixar versão estável; copiar configuração sem sobrescrever segredos; realizar backup
verificado antes da mudança; testar upgrade em cópia isolada e serializar migrações.
Validar saúde, permissões, filas e fluxos antes de liberar escrita. Para regressão,
usar versão anterior apenas quando compatível com o esquema; caso contrário,
recuperar o conjunto consistente em ambiente novo e validar antes de trocar acesso.
Não executar downgrade destrutivo nem apagar bancos/volumes como fluxo padrão.
