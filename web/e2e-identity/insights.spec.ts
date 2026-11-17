import { test, expect, type Page } from './authenticated';
import type { APIRequestContext, Browser } from '@playwright/test';

async function mutate(api: APIRequestContext, path: string, data: unknown, method = 'POST') {
  const token = await (await api.get('/api/v1/auth/csrf')).json();
  const response = await api.fetch('/api/v1' + path, {
    method, data,
    headers: { 'X-CSRF-Token': token.csrf_token, 'Idempotency-Key': crypto.randomUUID() },
  });
  expect(response.ok()).toBeTruthy();
  return response.json();
}

async function technician(browser: Browser, admin: Page) {
  const suffix = crypto.randomUUID();
  const email = `insights-${suffix}@example.test`;
  const invitation = await mutate(admin.request, '/invitations', { email, role: 'tecnico' });
  const context = await browser.newContext({ baseURL: test.info().project.use.baseURL });
  await mutate(context.request, '/invitations/accept', {
    email, password: `Ficticio!${crypto.randomUUID()}`, name: `Técnico fictício ${suffix.slice(0, 8)}`,
    token: invitation.invitation_path.split('=')[1],
  });
  const me = await (await context.request.get('/api/v1/me')).json();
  return { context, me };
}

async function draft(api: APIRequestContext, clientId: string, title: string, restricted = false) {
  const source = await mutate(api, '/records', {
    client_id: clientId, type: 'conhecimento', category: 'impressão', system: 'SGBR fictício',
    texto_original: 'Relato fictício: impressão apresentou 0x80070005; CFOP 5102 informado, sem verificação.',
  });
  const item = await (await api.get(`/api/v1/knowledge/articles/${source.article_id}`)).json();
  const edited = await mutate(api, `/knowledge/articles/${item.id}`, {
    revision: item.revision, title, problem: 'Impressão fictícia apresentou 0x80070005.',
    context: 'Cenário fictício relatado.', confirmed_cause: '',
    procedure: 'Procedimento informado pelo autor fictício.', result: 'Resultado relatado.',
    text: source.texto_original, keywords: ['impressão', '0x80070005'],
    category: 'impressão', system: 'SGBR fictício', client_id: restricted ? clientId : null,
  }, 'PATCH');
  return { source, item: edited };
}

async function action(api: APIRequestContext, item: { id: string; revision: number }, name: string, extra = {}) {
  return mutate(api, `/knowledge/articles/${item.id}/actions`, { revision: item.revision, action: name, ...extra });
}

test('revisão editorial humana, devolução, publicação, busca com destaque e origem preservada', async ({ page, browser }) => {
  const tech = await technician(browser, page);
  try {
    const client = await mutate(page.request, '/clients', { name: `Cliente editorial fictício ${crypto.randomUUID()}` });
    const title = `Impressão fictícia ${crypto.randomUUID()}`;
    const { source, item } = await draft(tech.context.request, client.id, title);
    await action(tech.context.request, item, 'enviar');
    await page.goto(`/#artigo=${item.id}`);
    const area = page.getByRole('region', { name: 'Base de Conhecimento', exact: true });
    let detail = area.getByRole('article', { name: 'Abrir artigo', exact: true });
    await expect(detail.getByText('⚠ Código fiscal não verificado: confira no contexto e na fonte.', { exact: true })).toBeVisible();
    await expect(detail.getByRole('button', { name: 'Publicar artigo', exact: true })).toBeDisabled();
    await detail.getByRole('textbox', { name: 'Comentário de devolução ou motivo de arquivamento', exact: true }).fill('Confira o procedimento informado no relato fictício.');
    await detail.getByRole('button', { name: 'Devolver ao autor', exact: true }).click();
    await expect(detail.getByText(/↩ Devolvido ao autor · Versão/)).toBeVisible();
    const authorPage = await tech.context.newPage();
    await authorPage.goto(`/#artigo=${item.id}`);
    const authorDetail = authorPage.getByRole('article', { name: 'Abrir artigo', exact: true });
    await authorDetail.getByRole('textbox', { name: 'Procedimento', exact: true }).fill('Procedimento fictício conferido pelo autor, sem acrescentar diagnóstico.');
    await authorDetail.getByRole('button', { name: 'Salvar rascunho', exact: true }).click();
    await expect(authorDetail.getByText(/↩ Devolvido ao autor · Versão 5/)).toBeVisible();
    await authorDetail.getByRole('button', { name: 'Enviar para revisão', exact: true }).click();
    await expect(authorDetail.getByText(/◷ Aguardando revisão · Versão 6/)).toBeVisible();
    await page.reload();
    detail = area.getByRole('article', { name: 'Abrir artigo', exact: true });
    await detail.getByLabel('Conferi o conteúdo do artigo e confirmo a publicação humana.', { exact: true }).check();
    await expect(detail.getByRole('button', { name: 'Publicar artigo', exact: true })).toBeDisabled();
    await detail.getByLabel('Conferi incertezas, códigos fiscais e avisos de possível credencial.', { exact: true }).check();
    await detail.getByRole('button', { name: 'Publicar artigo', exact: true }).click();
    await expect(detail.getByText(/✓ Publicado · Versão 7/)).toBeVisible();
    await expect(detail.getByText('Não informada', { exact: true })).toBeVisible();
    await detail.getByRole('button', { name: 'Versões e diferenças', exact: true }).click();
    await expect(detail.locator('summary').filter({ hasText: 'Versão 5' })).toBeVisible();
    await area.getByLabel('Termo, código ou mensagem de erro', { exact: true }).fill(title);
    await area.getByRole('button', { name: 'Pesquisar artigos', exact: true }).click();
    const cards = area.locator('.workspace-list article');
    await expect(cards).toHaveCount(1);
    await area.getByLabel('Termo, código ou mensagem de erro', { exact: true }).fill('0x80070005');
    await area.getByRole('button', { name: 'Pesquisar artigos', exact: true }).click();
    await expect(cards.filter({ hasText: title })).toHaveCount(1);
    await expect(cards.filter({ hasText: title }).locator('mark').first()).toBeVisible();
    const origin = await (await page.request.get(`/api/v1/records/${source.id}`)).json();
    expect(origin.ocorrido_em).toBe(source.ocorrido_em);
    expect(origin.enviado_em).toBe(source.enviado_em);
    await detail.getByRole('link', { name: 'Abrir registro de origem', exact: true }).click();
    await expect(page.getByRole('region', { name: 'Atendimentos', exact: true }).locator('.workspace-detail')).toContainText(source.texto_original);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  } finally { await tech.context.close(); }
});

test('artigo restrito só aparece no cliente correto e sai da busca ao arquivar', async ({ page, browser }) => {
  const tech = await technician(browser, page);
  try {
    const own = await mutate(page.request, '/clients', { name: `Restrito fictício ${crypto.randomUUID()}` });
    const other = await mutate(page.request, '/clients', { name: `Outro fictício ${crypto.randomUUID()}` });
    const title = `Restrito impressão ${crypto.randomUUID()}`;
    const { item } = await draft(tech.context.request, own.id, title, true);
    const sent = await action(tech.context.request, item, 'enviar');
    const published = await action(page.request, sent, 'publicar', { human_reviewed: true, warnings_reviewed: true });
    await page.goto('/');
    await page.getByRole('button', { name: 'Base de Conhecimento', exact: true }).click();
    const area = page.getByRole('region', { name: 'Base de Conhecimento', exact: true });
    await area.getByLabel('Termo, código ou mensagem de erro', { exact: true }).fill(title);
    await area.getByRole('button', { name: 'Pesquisar artigos', exact: true }).click();
    await expect(area.locator('.workspace-list article')).toHaveCount(0);
    await area.getByRole('combobox', { name: 'Cliente', exact: true }).selectOption(other.id);
    await area.getByRole('button', { name: 'Pesquisar artigos', exact: true }).click();
    await expect(area.locator('.workspace-list article')).toHaveCount(0);
    await area.getByRole('combobox', { name: 'Cliente', exact: true }).selectOption(own.id);
    await area.getByRole('button', { name: 'Pesquisar artigos', exact: true }).click();
    await expect(area.locator('.workspace-list article')).toHaveCount(1);
    const ticket = await mutate(page.request, '/records', { client_id: other.id, type: 'chamado', texto_original: 'Impressão fictícia 0x80070005', category: 'impressão' });
    const suggestions = await (await page.request.get(`/api/v1/tickets/${ticket.ticket_id}/suggestions`)).json();
    expect(JSON.stringify(suggestions)).not.toContain(item.id);
    await page.goto(`/#artigo=${published.id}`);
    const detail = area.getByRole('article', { name: 'Abrir artigo', exact: true });
    await detail.getByRole('textbox', { name: 'Comentário de devolução ou motivo de arquivamento', exact: true }).fill('Procedimento fictício substituído após revisão.');
    await detail.getByRole('button', { name: 'Arquivar artigo', exact: true }).click();
    await expect(detail.getByText(/□ Arquivado · Versão/)).toBeVisible();
    expect((await (await page.request.get(`/api/v1/knowledge/search?client_id=${own.id}&q=${encodeURIComponent(title)}`)).json()).total).toBe(0);
    expect((await (await page.request.get(`/api/v1/knowledge/search?status=arquivado&client_id=${own.id}&q=${encodeURIComponent(title)}`)).json()).total).toBe(1);
  } finally { await tech.context.close(); }
});

test('relatórios exibem fatos distintos, alternativas do gráfico e CSV auditado', async ({ page }) => {
  const client = await mutate(page.request, '/clients', { name: `=Cliente fictício ${crypto.randomUUID()}` });
  const confirmed = await mutate(page.request, '/records', { client_id: client.id, type: 'finalizacao', texto_original: 'Conclusão fictícia conferida.' });
  await mutate(page.request, `/records/${confirmed.id}/actions`, { revision: confirmed.revision, action: 'confirmar' });
  await mutate(page.request, '/records', { client_id: client.id, type: 'finalizacao', texto_original: 'Outra finalização fictícia ainda pendente.' });
  const opened = await mutate(page.request, '/records', { client_id: client.id, type: 'chamado', texto_original: 'Chamado fictício para relatório.' });
  const ticket = await (await page.request.get(`/api/v1/tickets/${opened.ticket_id}`)).json();
  await mutate(page.request, `/tickets/${ticket.id}`, { revision: ticket.revision, status: 'resolvido', completion_description: 'Ação fictícia executada para relatório.' }, 'PATCH');
  await page.goto('/');
  await page.getByRole('button', { name: 'Relatórios', exact: true }).click();
  const area = page.getByRole('region', { name: 'Relatórios', exact: true });
  await area.getByRole('combobox', { name: 'Cliente', exact: true }).selectOption(client.id);
  await area.getByRole('combobox', { name: 'Período', exact: true }).selectOption('inicio');
  const loaded = page.waitForResponse(r => r.url().includes('/api/v1/reports?') && r.url().includes(client.id));
  await area.getByRole('button', { name: 'Aplicar filtros', exact: true }).click();
  expect((await loaded).ok()).toBeTruthy();
  for (const label of ['Finalizações confirmadas', 'Finalizações aguardando revisão']) {
    await expect(area.locator('.metric-cards article').filter({ has: page.getByRole('heading', { name: label, exact: true }) }).locator('.metric-number')).toHaveText('1');
  }
  const actions = area.getByRole('table', { name: 'Período selecionado', exact: true });
  await expect(actions.getByRole('row').filter({ has: page.getByRole('cell', { name: 'Resolveu', exact: true }) })).toContainText('1');
  await expect(actions.getByRole('row').filter({ has: page.getByRole('cell', { name: 'Encerrou', exact: true }) })).toContainText('1');
  await expect(area.getByText('Estatísticas refletem apenas atendimentos registrados.', { exact: true })).toBeVisible();
  await expect(area).not.toContainText(/\b(?:ranking|posição|domina|precisa de curso|precisa contratar|incompetente)\b/i);
  await expect(area.getByRole('img', { name: 'Registros por período', exact: true })).toBeVisible();
  await expect(area.getByRole('table', { name: 'Tabela alternativa do gráfico', exact: true })).toBeVisible();
  await area.locator('summary').filter({ hasText: 'Distribuição de registros e ações' }).click();
  await expect(area.getByRole('table', { name: 'Distribuição de registros e ações', exact: true })).toBeVisible();
  const downloadPromise = page.waitForEvent('download');
  await area.getByRole('button', { name: 'Exportar CSV', exact: true }).click();
  const download = await downloadPromise;
  const stream = await download.createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream!) chunks.push(Buffer.from(chunk));
  const csv = Buffer.concat(chunks).toString('utf8');
  expect(csv).toContain("'=Cliente fictício");
  expect(csv).toContain('Estatísticas refletem apenas atendimentos registrados.');
  expect(csv).toContain(confirmed.id);
  const audit = await (await page.request.get('/api/v1/audit-events')).json();
  expect(JSON.stringify(audit)).toContain('relatorio_exportado');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
});

test('técnico vê somente números próprios e equipe criada mantém o escopo', async ({ page, browser }) => {
  const tech = await technician(browser, page);
  try {
    const client = await mutate(page.request, '/clients', { name: `Escopo fictício ${crypto.randomUUID()}` });
    await mutate(tech.context.request, '/records', { client_id: client.id, type: 'finalizacao', texto_original: 'Registro fictício do próprio técnico.' });
    const admin = await (await page.request.get('/api/v1/me')).json();
    const teamName = `Equipe fictícia ${crypto.randomUUID()}`;
    await page.goto('/');
    await page.getByRole('button', { name: 'Relatórios', exact: true }).click();
    const area = page.getByRole('region', { name: 'Relatórios', exact: true });
    await area.getByText('Equipes dos relatórios', { exact: true }).click();
    const create = area.locator('form').filter({ has: page.getByRole('button', { name: 'Criar equipe', exact: true }) });
    await create.getByLabel('Nome da equipe', { exact: true }).fill(teamName);
    await create.getByLabel(tech.me.name, { exact: true }).check();
    await create.getByRole('button', { name: 'Criar equipe', exact: true }).click();
    await expect(area.getByRole('combobox', { name: 'Equipe', exact: true }).getByRole('option', { name: teamName, exact: true })).toHaveCount(1);
    const personal = await tech.context.newPage();
    await personal.goto('/');
    await personal.getByRole('button', { name: 'Relatórios', exact: true }).click();
    const own = personal.getByRole('region', { name: 'Relatórios', exact: true });
    await expect(own.getByText('Escopo: somente os próprios números', { exact: true })).toBeVisible();
    await expect(own.getByRole('combobox', { name: 'Pessoa / responsável', exact: true }).locator('option')).toHaveCount(2);
    await expect(own.getByRole('combobox', { name: 'Pessoa / responsável', exact: true }).getByRole('option', { name: tech.me.name, exact: true })).toHaveCount(1);
    await expect(own.getByRole('button', { name: 'Criar equipe', exact: true })).toHaveCount(0);
    expect((await tech.context.request.get(`/api/v1/reports?responsible_id=${admin.id}`)).status()).toBe(403);
    const token = await (await tech.context.request.get('/api/v1/auth/csrf')).json();
    const denied = await tech.context.request.post('/api/v1/reports/export', { data: { responsible_id: admin.id }, headers: { 'X-CSRF-Token': token.csrf_token } });
    expect(denied.status()).toBe(403);
    expect(await personal.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  } finally { await tech.context.close(); }
});
