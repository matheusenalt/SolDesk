# Evolução do produto

Estado implementado/testado em [STATUS](../STATUS.md); intenção em [VISAO](VISAO.md).
Preservar FastAPI/React/PostgreSQL/RLS, segurança, versões e horários. Não reescrever o núcleo.

| Ordem | Evolução | Reuso e aceite principal |
|---|---|---|
| 1 | Consolidação documental, identidade e gravação web | Uma interface responsiva, logo oficial, contraste, microfone e PWA sem cache sensível |
| 2 | Validação humana independente por versão | Reutilizar Record/versões; separar áudio, fidelidade e resolução; outro leitor autorizado; concorrência/legado íntegro |
| 3 | Atendimentos contínuos e atividade interna | Atualizações append-only, responsável/próxima ação e conclusão; não fingir cliente para trabalho interno |
| 4 | Catálogo de sistemas | Entidade por organização e vínculo de cliente; preservar texto legado e contexto das versões |
| 5 | Tarefas | Pessoa/equipe, cliente opcional, data/prioridade/status; conclusão simples, independente de chamado |
| 6 | Calendário interno | Operação independente; integração CalDAV opcional em adaptador próprio |
| 7 | Evolução de chamados | Prazo, inatividade descrita como falta de atualização, aceite/devolução e caso solicitante=responsável configurável |
| 8 | Pesquisa global | Reusar PostgreSQL FTS/pg_trgm; códigos exatos primeiro; respeitar visibilidade por objeto e sinalizar não validado |
| 9 | Confirmação técnica de conhecimento | Evento vinculado à versão, data/autor, obsolescência/revalidação sem apagar histórico |
| 10 | Operação e piloto | CSV com prévia/deduplicação, anexos grandes, quotas, HTTPS, privacidade, backup/restauração e instalador Linux homologados |

Embeddings pequenos, pesquisa por voz, conectores externos e Nextcloud dependem
de benefício medido e aprovação própria. Não instalar modelos nem vincular núcleo
a uma empresa externa. Sem OCR, app nativo ou produção implícitos nesse planejamento.
Importação/sincronização futura precisa de identidade externa única, procedência,
conflitos explícitos e proteção dos campos locais; ausência na fonte não autoriza exclusão.
Logo, regras de validação/aceite, retenção e plataformas homologadas dependem de decisão.

Situação visual atual: paleta provisória, ações principais e responsividade
ajustadas e testadas localmente. A identidade definitiva ainda depende da logo
oficial; não foram criados ícones PWA nem substituto da marca. Ver
[identidade](IDENTIDADE_SOL.md) e [estado real](../STATUS.md).

Gravação web agora inclui pausa compatível, interrupção, arquivo vazio e recuperação
de resposta perdida com a chave original. Manifesto inicial existe sem service worker;
ícones oficiais e instalação PWA continuam pendentes. Testes e restrições operacionais
em [STATUS](../STATUS.md) e [operação de mídia](OPERACAO_MIDIA.md).

A base de dados/API da validação independente foi implementada. A interface com
ações individuais e etiquetas permanece pendente; a confirmação operacional
legada continua funcionando e não equivale à nova validação de fidelidade.

Atendimentos contínuos têm base de dados/API: mesmo ID, atualizações preservadas,
retomada, transferência e resultado. Atividade interna dispensa cliente mediante
marcador explícito. A interface dessa operação e a interface de validação independente
continuam pendentes. Próxima entrega prevista: conectar o painel a estes contratos,
mediante autorização; não considerar a experiência completa já disponível.

Interfaces de validação independente e atendimentos contínuos implementadas na web.
A abertura principal oferece Finalização e Em andamento; catálogos estruturados de
sistemas são a próxima evolução autorizada, mantendo campos e histórico textuais.
