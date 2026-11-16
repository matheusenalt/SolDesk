# Identidade Sol

Fonte única: [tokens.json](tokens.json). Execute `python scripts/tokens.py` para
gerar CSS web e constantes mobile; `--check` detecta deriva e mede contraste.

## Paleta oficial recebida

| Nome | HEX |
|---|---|
| zinc-50 | #fafafa |
| zinc-200 | #e4e4e7 |
| zinc-950 | #09090b |
| sol-gold | #f1a502 |
| sol-orange | #e45825 |
| sol-cream | #fbf8f2 |

`--spacing: 0.25rem` e `--radius-xl: 0.75rem` preservados. CSS usa `@theme`
do Tailwind v4. Tema claro: surface creme, panel zinc-50, texto zinc-950,
primary dourado, accent laranja e borda decorativa zinc-200. Tema escuro:
surface zinc-950 e panel zinc-900, textos zinc-50 e zinc-300.

## Extensões — não vêm da paleta Sol

Escala zinc padrão Tailwind: 900 #18181b, 800 #27272a, 600 #52525b,
400 #a1a1aa, 300 #d4d4d8. Usada em superfícies, texto secundário e contornos.
As bordas zinc-200/800 são decorativas; limites de controles interativos usam
`control-border` zinc-600/400 com contraste de pelo menos 3:1.

Feedback: sucesso green-800 #166534 / green-300 #86efac; erro red-800 #991b1b /
red-300 #fca5a5; aviso amber-800 #92400e / amber-300 #fcd34d; informação
blue-800 #1e40af / blue-300 #93c5fd (claro/escuro). Essas cores são apenas tokens
de estado, sempre acompanhados por ícone e texto, sem depender só de cor.
Todos os textos de feedback superam 4,5:1 sobre surface e panel nos dois temas.

## Contraste

Zinc-950 sobre dourado: 9,59:1; sobre laranja: 5,42:1; sobre creme: 18,77:1.
Texto de ações é escuro. Branco sobre dourado/laranja e texto corrente dourado
ou laranja sobre creme são proibidos. Acentos só em preenchimentos ou detalhes.
Foco de teclado tem contorno de texto; respeitar preferência de movimento reduzido.
O teste calcula todos os pares de texto/feedback e contornos de controles usados;
falha abaixo de 4,5:1 para texto e 3:1 para limites interativos. Não substitui QA
de teclado, leitor de tela e layout. Mobile espelhará os mesmos valores gerados.
