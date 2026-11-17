# Identidade Sol — aplicação provisória

**Logo oficial não localizada no projeto em 16/11/2026. Identidade definitiva pendente.**
Não foi criada outra logo. A interface usa o nome SolDesk em texto; símbolos de sol
antes usados como marca provisória foram retirados. Não há ícones PWA nem app nativo.

## Fonte única e paleta

[tokens.json](tokens.json) é a fonte da paleta; `python scripts/tokens.py` gera
[tokens.css](../web/src/tokens.css). `--check` detecta deriva e mede contraste.

| Token | Cor provisória | Uso |
|---|---|---|
| sol-gold | #F7C400 | Ação principal e destaque moderado |
| sol-orange | #FF7A00 | Detalhe decorativo na navegação ativa, com sublinhado de alto contraste e aria-current |
| sol-black | #0B0B0B | Texto claro e superfície do tema escuro |
| sol-cream | #F8F8F5 | Superfície clara |
| white | #FFFFFF | Painéis claros |

Espaçamento 0,25rem e raio 0,75rem preservados; Tailwind v4 e componentes React
existentes reaproveitados. Escalas zinc/feedback são extensões semânticas, não logo.
Os valores deverão ser conferidos com o arquivo oficial antes de concluir a identidade.

## Contraste e acessibilidade

Medições do gerador: preto sobre amarelo **12,04:1**, sobre laranja **7,53:1**;
texto sobre superfície clara **18,50:1**, sobre painel branco **19,68:1**.
Menor par de texto/feedback: **6,66:1**; contorno interativo mínimo: **6,91:1**.
São 32 pares nos temas claro/escuro, acima de 4,5:1 para texto e 3:1 para contornos.
Não usar texto pequeno amarelo/branco sobre amarelo ou laranja.
Laranja sobre branco não atinge 3:1; por isso não é o único indicador de seleção.
A aba ativa tem sublinhado na cor do texto do tema, negrito e estado acessível.

Foco visível: contorno sólido de 3 px, afastamento de 4 px; cor de texto do tema.
O teste navega com Tab e mede espessura, afastamento e contraste no navegador,
nos dois temas. Feedback continua com texto/ícone, sem depender somente de cor.
Botões/controles têm alvo mínimo de 44 × 44 px; checkbox/radio usam o label como alvo.

## Responsividade e navegação

Mesma interface para desktop e celular, formulários em uma coluna até 760 px,
abas com quebra, campos sem largura mínima que estoure a página e controles de áudio
preservados. Tabelas extensas mantêm contêiner de rolagem próprio, sem alargar a página.
Ações destacadas: **Abrir atendimento** (formulário existente) e **Pesquisar**
(artigos publicados, explicitamente identificado; não é busca global).
Somente finalização, chamado e conhecimento são oferecidos, conforme a API atual.

Testes autenticados e dispositivos efetivamente verificados: [STATUS](../STATUS.md).
Emulação e screenshots não homologam aparelho físico, leitor de tela ou Safari/iOS.
