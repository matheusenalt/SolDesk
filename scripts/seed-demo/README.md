# Demonstração fictícia no produto

Em uma instalação **Cloud não produtiva**, após o setup:

- PowerShell: `./scripts/seed-demo/run.ps1`.
- Bash: `bash scripts/seed-demo/run.sh`.

Cria `demo-aurora` e `demo-horizonte`, cada uma com um administrador, um técnico
e um cliente diferente. E-mails terminam em `example.test`. Senhas aleatórias
são mostradas somente na execução que criou cada empresa; não há senhas fixas.
Guarde-as de modo privado. Repetir não altera senhas nem duplica os dados.

No Community, use `python -m app.manage bootstrap` através do serviço `migrate`;
duas empresas são incompatíveis com esse modo. Não mude para Cloud em uma
instalação real apenas para testar. Use ambiente próprio com dados inventados.

`seed-demo --json` emite as novas credenciais em stdout para automação local;
capture-as em variáveis de ambiente, nunca em Git, arquivos de log ou CI pública.
