# Infraestrutura

O Compose fica em `../compose.yaml`. Nginx e Dockerfiles ficam junto aos aplicativos.
PostgreSQL sem porta publicada, volume nomeado persistente e migração antes da API.
O usuário do PostgreSQL desta fase é exclusivo do bootstrap/migrações. Antes de
criar entidades de negócio (fase 02), separar papel runtime sem superusuário/dono
e papel de migração e testar RLS; o papel inicial do Postgres é superusuário.
