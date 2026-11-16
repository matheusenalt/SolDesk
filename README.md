# SolDesk

Plataforma independente de suporte com histórico, chamados e conhecimento.
**Fase atual: 01, estrutura inicial e aceite Docker/PostgreSQL aprovados no Windows/WSL 2.**
Não há login, clientes ou dados de negócio nesta fase.

## Instalação do zero

1. Instale Git e Docker com Compose. Windows 10/11: Docker Desktop com backend
   WSL 2, virtualização habilitada e requisitos atuais do fabricante atendidos.
   Linux: Docker Engine e plugin Compose. Tenha um navegador atualizado.
2. Abra esta pasta em um terminal. Não é preciso instalar Python, Node ou banco
   separadamente para usar a versão em contêineres.
3. Execute no PowerShell: `powershell -ExecutionPolicy Bypass -File scripts/setup.ps1`.
   No Linux: `bash scripts/setup.sh`.
4. Abra http://localhost:8080 e http://localhost:8000/docs.
5. Verifique http://localhost:8000/api/v1/health e
   http://localhost:8000/api/v1/server-info.

Os scripts copiam `.env.example` e geram uma senha aleatória local para o banco.
Não imprimem a senha, não criam credenciais de aplicação e não apagam volumes.
A instalação não depende de chave de IA, GPU nem serviço pago.

## Portas

| Serviço | Endereço padrão | Alteração |
|---|---|---|
| Web | http://localhost:8080 | `WEB_PORT` no `.env` |
| API/OpenAPI | http://localhost:8000/docs | `API_PORT` no `.env` |
| Vite (perfil dev) | http://localhost:5173 | `DEV_PORT` no `.env` |
| PostgreSQL | somente rede interna | sem porta publicada |

Atualize também `CORS_ORIGINS` se trocar portas. Para desenvolvimento com reload:
`docker compose --profile dev up -d --build db migrate api-dev web-dev`.

Leia [TESTE_LOCAL.md](TESTE_LOCAL.md) para comandos manuais, desenvolvimento fora
do Docker e validações. [STATUS.md](STATUS.md) informa o que foi realmente testado;
[ARQUITETURA.md](ARQUITETURA.md) explica os limites da fase.

Os arquivos originais de requisitos estão em [SolDesk_Prompts_v2](SolDesk_Prompts_v2/).
## Licença

Copyright (C) 2026 contribuidores do SolDesk.

O código próprio do SolDesk é disponibilizado sob a **GNU Affero General Public
License, versão 3 somente** (`AGPL-3.0-only`), sem garantia. O texto oficial,
inalterado, está em [LICENSE](LICENSE).

São permitidas instalações próprias, modificações, contribuições e hospedagem
comercial, observadas as condições da licença. Versões modificadas que atendam
usuários pela rede devem oferecer a esses usuários o código-fonte correspondente,
conforme a seção 13. A oferta comercial não dispensa essas obrigações.

Dependências mantêm suas próprias licenças. Consulte a
[revisão de licenças](docs/LICENCAS.md) e [como contribuir](CONTRIBUTING.md).
