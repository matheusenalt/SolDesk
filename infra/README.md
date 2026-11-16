# Infraestrutura

[Compose](../compose.yaml) mantém PostgreSQL e Redis internos e volumes persistentes.
API usa runtime sem superusuário/BYPASSRLS/ownership; migrações usam papel separado.
Nginx e Dockerfiles ficam junto aos aplicativos; imagens runtime não usam root.
Setup espera banco saudável e aplica migrações sem apagar dados. Desktop/celular
usam a mesma web; não há pipeline nativo.

[Instalação](../docs/INSTALACAO.md), [testes](../TESTE_LOCAL.md),
[segurança](../docs/SEGURANCA.md), [mídia](../docs/OPERACAO_MIDIA.md)
e [backup/restauração ainda não homologados](../docs/BACKUP.md).
