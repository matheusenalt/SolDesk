# Permissões das fases 02–03

Todas as operações exigem sessão válida e vínculo ativo na organização corrente.
O tenant é recuperado da sessão persistida, nunca aceito como credencial do cliente.

| Recurso e ação | Administrador | Gestor | Técnico |
| --- | --- | --- | --- |
| Consultar, buscar e cadastrar/editar clientes | Sim | Sim | Sim |
| Consultar referências externas do cliente | Sim | Sim | Sim |
| Consultar equipe | Sim | Sim | Não |
| Criar convite ou integrante com senha temporária | Sim | Não | Não |
| Alterar papel ou desativar integrante | Sim | Não | Não |
| Redefinir senha de integrante exclusivo | Sim | Não | Não |
| Alterar nome, fuso e configurações da organização | Sim | Não | Não |
| Consultar auditoria administrativa | Sim | Sim | Não |
| Alterar a própria senha, sair e encerrar todas as próprias sessões | Sim | Sim | Sim |
| Selecionar outra organização com vínculo ativo | Sim | Sim | Sim |
| Acessar dados de outra organização sem vínculo | Não | Não | Não |

Todos os membros ativos veem todos os clientes da organização; restrição por
cliente é evolução futura. O técnico não lista equipe nem promove a si mesmo.
Um gestor não obtém acesso administrativo pela interface ou chamada direta à API.
Relatórios e publicação de artigos não têm autorização ativa nesta fase.

## Registros e chamados

| Recurso/ação | Regra na organização corrente |
| --- | --- |
| Criar registro/chamado | Qualquer membro ativo; autoria fixada no usuário autenticado |
| Listar opções de atribuição/menção | Membro ativo recebe somente ID e nome dos ativos |
| Consultar registros provisórios | Autor; gestão; técnico participante do chamado vinculado |
| Consultar finalizações confirmadas | Todos os membros ativos |
| Editar/conferir/devolver/enviar registro | Somente autor, conforme estado |
| Confirmar finalização individual/em lote | Somente autor, inclusive quando o solicitante é gestor/admin |
| Cancelar registro com motivo | Autor ou gestão; chamado enviado usa ciclo do Ticket |
| Derivar um registro acessível | Qualquer membro com acesso ao original, novo rascunho próprio |
| Consultar chamados/conversa | Gestão: todos; técnico: abertos por ele, atribuídos ou dos quais participa |
| Transferir, mudar prioridade/categoria/estado ou pedir esclarecimento | Responsável atual ou gestão |
| Encerrar chamado resolvido | Quem abriu ou gestão |
| Comentar/responder/mencionar | Membro com acesso ao chamado; menção só a integrante ativo da mesma empresa |
| Consultar/marcar notificação | Somente destinatário, sem exceção administrativa |
| Apagar versões, comentários, eventos ou registros | Não disponível |

Transferência mantém participantes anteriores; menção adiciona o mencionado como
participante. Essa visibilidade permite acompanhar respostas, sem dar permissão
de gestão do chamado. Finalizações não têm revisão do gestor: nenhuma
configuração pode habilitar confirmação de relato alheio. Ver [ESTADOS](ESTADOS.md).

A organização é bloqueada por linha durante alterações de integrantes, evitando
que requisições concorrentes removam/rebaixem todos os administradores. Papel e
situação são sempre reconsultados; desativação ou mudança de papel revoga as
sessões daquele usuário nessa organização.

A senha pertence à identidade global do usuário. O administrador só pode redefinir
a senha de uma identidade vinculada exclusivamente à sua organização. Contas
compartilhadas entre empresas exigem que o titular use a alteração autenticada
da própria senha. Isso impede que uma empresa assuma o acesso a outras empresas.
Não existe recuperação pública que revele a existência de um e-mail, nem SMTP.
