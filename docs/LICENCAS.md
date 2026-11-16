# Licenciamento do SolDesk e dependências

## Código próprio

Copyright (C) 2026 contribuidores do SolDesk. GNU AGPL v3 somente
(`AGPL-3.0-only`), escolhida pelo titular. [LICENSE](../LICENSE) contém o texto
original de https://www.gnu.org/licenses/agpl-3.0.txt, sem alterações.
SHA-256 do arquivo recebido:
`0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0`.

Instalação própria e hospedagem comercial são permitidas sob os termos da licença.
As obrigações de disponibilizar fonte correspondente e preservar avisos se aplicam
conforme a distribuição e, para versões modificadas acessíveis pela rede, seção 13.
O código-fonte oficial está em https://github.com/matheusenalt/SolDesk.

## Revisão das dependências da fase 01

Inventário obtido dos metadados das 38 distribuições Python instaladas nas versões
exatas do lock e dos 272 pacotes npm do lock (inclui ferramentas e opcionais de
outras plataformas). Evidências: [Python](LICENCAS_PYTHON.json) e
[npm](LICENCAS_NPM.json). Reproduzir com `python scripts/audit_licenses.py` no
ambiente de desenvolvimento. O script exige as versões Python iguais ao lock.

| Licenças identificadas | Avaliação e condições |
| --- | --- |
| MIT, ISC, BSD-2-Clause, BSD-3-Clause, 0BSD, BlueOak-1.0.0 | Permissivas; preservar atribuições, avisos e termos aplicáveis ao redistribuir. |
| Apache-2.0, PSF-2.0, MIT AND PSF-2.0 | Compatíveis com a adoção de AGPL v3 no código próprio; preservar licenças e NOTICE quando existente. `packaging` oferece Apache-2.0 OR BSD-2-Clause. |
| LGPL-3.0-only: psycopg e psycopg-binary | Bibliotecas separadas, sem modificação local. Preservar LGPL, acesso ao fonte correspondente e possibilidade de substituição/religação conforme a forma de distribuição. Não relicenciar essas bibliotecas como código próprio. |
| MPL-2.0: certifi e lightningcss/opcionais | Copyleft por arquivo; manter avisos, licença e fonte dos arquivos cobertos ao redistribuir. Não houve modificação nem incorporação de seus fontes no SolDesk. lightningcss integra as ferramentas de build. |
| CC-BY-4.0: caniuse-lite | Dados usados pelas ferramentas de build; preservar atribuição/licença e indicar mudanças se esses dados forem redistribuídos. Não é licença do código próprio do SolDesk. |

Não foi identificada licença incompatível no conjunto inventariado e no uso atual.
O `colorama` não declara expressão SPDX nos metadados; seu arquivo LICENSE.txt
instalado foi lido e contém BSD de três cláusulas. Todos os pacotes npm possuem
licença declarada no lock. Isso é revisão de dependências declaradas e de suas
condições, não certificação jurídica ou análise exaustiva de cada arquivo binário.

## Distribuição e imagens

Não são enviados `.venv`, `node_modules`, ferramentas baixadas, caches, bancos ou
imagens Docker ao Git. Dependências são obtidas pelos gerenciadores com seus avisos.
As imagens referenciadas têm componentes com licenças próprias: Python (PSF), Node
(MIT e componentes terceiros), PostgreSQL (PostgreSQL License), Nginx (BSD e
componentes terceiros), Debian/Alpine e bibliotecas nativas. Psycopg binary também
inclui bibliotecas cliente; consultar seus avisos ao redistribuir wheels ou imagens.

Publicar imagens/binários exige preservar os avisos de todos os componentes e
cumprir a entrega de fonte correspondente quando exigida. O inventário de pacotes
Python/npm não é um SBOM completo das imagens de sistema operacional. Nenhuma
imagem/binário é publicada como parte deste primeiro push de código-fonte.

## Fontes primárias

- [Texto oficial GNU AGPL v3](https://www.gnu.org/licenses/agpl-3.0.html).
- [Lista de licenças e compatibilidade da FSF](https://www.gnu.org/licenses/license-list.html).
- [Compatibilidade Apache/GPL v3](https://www.apache.org/licenses/GPL-compatibility.html).
- [MPL 2.0 e perguntas frequentes](https://www.mozilla.org/en-US/MPL/2.0/FAQ/).
- [Instalação e bibliotecas incluídas no Psycopg](https://www.psycopg.org/psycopg3/docs/basic/install.html).

## Revisão antes da publicação

Revisados os arquivos fonte, scripts, configuração, requisitos e documentação do
projeto. Os lockfiles são preservados; dependências não estão vendorizadas.
Busca por padrões comuns de tokens/chaves e revisão de dados de exemplo sem
credencial identificada. Dados de testes são fictícios. Não foram acessados nem
copiados arquivos de outros projetos ou empregadores. Uma busca por padrões não
prova a origem de todo código nem substitui auditoria independente.
