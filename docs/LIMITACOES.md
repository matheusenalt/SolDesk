# Limitações e capacidade

Confirmado por código, salvo indicação. Estes limites não são SLA nem garantia de capacidade.

| Área | Limitação atual e efeito |
|---|---|
| Upload | Padrão 25 MiB; Settings/Nginx têm teto 64 MiB. 80 MB não são suportados |
| Memória/I/O | Upload acumula bytes e faz cópia; download lê tudo. Storage/antivírus síncronos no fluxo async; impacto sob concorrência não medido |
| Rede | Timeout de upload web de 60 s; aumentar tamanho sozinho não resolve reenvio ou consumo |
| Filas | Recibo/lease/retry existem; dispatcher consulta periodicamente. Sem benchmark representativo |
| Relatórios | Carrega até 10 mil registros/tickets, 50 mil eventos/consultas e 20 mil intervalos antes do recorte; retorna 422 em excesso, sem truncar silenciosamente |
| Revisão | Confirmação de finalização ainda restrita ao autor e acoplada ao ciclo do registro; validação independente por versão é planejada |
| Clientes | Todos os membros ativos acessam clientes da organização; contexto de artigo restrito não é ACL adicional |
| Integração | Referência externa sem unicidade; edição substitui referências. Não há importação CSV ou sincronização pronta |
| Migração | Lock de preparação termina antes do upgrade Alembic; corrida não reproduzida. Usar executor único |
| Saúde | /health verifica banco/Installation; não comprova head compatível nem todos os subsistemas |
| Auditoria | Snapshots duplicam conteúdo de relatos; retenção precisa abranger versões, auditoria e backups |

## Áudio e provedores opcionais

Mock não reconhece fala; usa apenas texto humano informado. Rules organiza marcadores
e exige fundamentação literal; nenhuma IA deve preencher fatos ausentes. faster-whisper
é opcional CPU/int8, com modelo local e sem download automático. Inferência real,
qualidade em português, carga/latência e pico de RAM continuam não homologados.
O modelo é carregado dentro de cada job; RQ usa processos filhos. Cache em módulo
não garante reaproveitamento entre jobs. Otimização depende de medição.
Perfil Whisper limita 3 GiB/2 CPUs, sem provar que um modelo cabe ou atende latência.
ClamAV real, Web Speech de fabricante, Safari/iOS físico e cargas produtivas não homologados.

## Estimativas para planejar testes

| Ambiente | Orçamento inicial estimado, não medição de capacidade |
|---|---|
| Notebook de 8 GB | Reservar cerca de 2–3 GB ao Docker conforme uso do host; mock/desabilitado; evitar dev/test/ASR simultâneos |
| VPS de teste | 2 vCPU, 2–4 GB RAM, SSD e espaço para mídia; medir com dados fictícios |
| Pequena equipe | 4 vCPU, 4–8 GB RAM e backup externo como ponto de partida para homologação, sem promessa de usuários/latência |

Amostras exploratórias locais de 16/11/2026: serviços principais somaram cerca de
410–463 MiB, excluindo host/Docker/WSL, caches, dev/test e picos. Não são medição
de carga, capacidade ou Whisper. Argon2 usa cerca de 64 MiB por operação; autenticações
concorrentes e buffers completos de upload também precisam de orçamento.
Antes de otimizar, medir consultas/índices, backlog, carga do modelo e uso do worker.
Ver [operação de mídia](OPERACAO_MIDIA.md) e [segurança](SEGURANCA.md).
