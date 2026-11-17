import { test, expect, type Page } from './authenticated';

async function mutation(page: Page, path: string, data: unknown) {
  const token = await (await page.request.get('/api/v1/auth/csrf')).json();
  const response = await page.request.post('/api/v1' + path, {
    data, headers: { 'X-CSRF-Token': token.csrf_token, 'Idempotency-Key': crypto.randomUUID() },
  });
  expect(response.ok()).toBeTruthy();
  return response.json();
}


async function start(page: Page) {
  const suffix = `${Date.now()}-${test.info().project.name}`;
  const client = await mutation(page, '/clients', { name: `Cliente fictício ${suffix}` });
  await page.goto('/');
  await page.getByRole('region', { name: 'Área da organização' }).getByRole('button', { name: 'Atendimentos', exact: true }).click();
  const area = page.getByRole('region', { name: 'Atendimentos', exact: true });
  await area.getByLabel('Cliente', { exact: true }).selectOption(client.id);
  return { area, client };
}

test('finalização revisada mantém o fato preciso e só então entra no histórico', async ({ page }) => {
  const { area, client } = await start(page);
  await area.getByLabel('Relato original', { exact: true }).fill('Procedimento fictício relatado pelo autor.');
  await area.getByText('Data com fuso explícito (opcional)', { exact: true }).click();
  await area.locator('input[name="explicit_time"]').fill('2026-01-15T14:35:27.123-03:00');
  const created = page.waitForResponse(r => r.url().endsWith('/api/v1/records') && r.request().method() === 'POST');
  await area.getByRole('button', { name: 'Enviar registro', exact: true }).click();
  const record = await (await created).json();
  expect(record.status).toBe('aguardando_revisao');
  await area.getByRole('button', { name: 'Histórico por cliente', exact: true }).click();
  await area.getByLabel('Cliente', { exact: true }).selectOption(client.id);
  await expect(area.getByText('Finalizações confirmadas: 0', { exact: true })).toBeVisible();
  await expect(area.locator('.work-card')).toHaveCount(0);
  await area.getByLabel('Incluir provisórios acessíveis', { exact: true }).check();
  await area.locator('.work-card').getByRole('button', { name: 'Consultar registro', exact: true }).click();
  let detail = area.locator('.workspace-detail');
  await detail.getByLabel('Texto conferido pelo autor', { exact: true }).fill('Procedimento fictício conferido sem alterar o instante.');
  await detail.getByRole('button', { name: 'Salvar alteração', exact: true }).click();
  await expect(detail.getByLabel('Texto conferido pelo autor')).toHaveValue('Procedimento fictício conferido sem alterar o instante.');
  await expect.poll(async () => (await (await page.request.get(`/api/v1/records/${record.id}`)).json()).revision).toBe(2);
  const edited = await (await page.request.get(`/api/v1/records/${record.id}`)).json();
  expect(edited.ocorrido_em).toBe(record.ocorrido_em);
  expect(edited.enviado_em).toBe(record.enviado_em);
  await detail.getByRole('button', { name: 'Conferi e confirmo', exact: true }).click();
  await expect(detail.getByText('✓ Confirmado · ✓ Histórico confirmado', { exact: true })).toBeVisible();
  await expect(area.getByText('Finalizações confirmadas: 1', { exact: true })).toBeVisible();
  await detail.getByLabel('Destino do novo rascunho', { exact: true }).selectOption('conhecimento');
  await detail.getByRole('button', { name: 'Derivar', exact: true }).click();
  detail = area.locator('.workspace-detail');
  await expect(detail.getByText('✎ Rascunho · ◷ Provisório — não confirmado', { exact: true })).toBeVisible();
  const list = await (await page.request.get('/api/v1/records')).json();
  const derived = list.items.find((item: { origem_record_id: string }) => item.origem_record_id === record.id);
  expect(derived.ocorrido_em).toBe(record.ocorrido_em);
  expect(derived.type).toBe('conhecimento');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
});

test('chamado urgente, esclarecimento, resposta, resolução e reabertura no mesmo código', async ({ page }) => {
  const { area } = await start(page);
  await area.getByLabel('Destino', { exact: true }).selectOption('chamado');
  await area.getByLabel('Relato original', { exact: true }).fill('Chamado urgente fictício, sem diagnóstico presumido.');
  await area.getByLabel('Prioridade', { exact: true }).selectOption('urgente');
  const created = page.waitForResponse(r => r.url().endsWith('/api/v1/records') && r.request().method() === 'POST');
  await area.getByRole('button', { name: 'Enviar registro', exact: true }).click();
  const record = await (await created).json();
  expect(record.status).toBe('enviado');
  expect(record.ticket_id).toBeTruthy();
  await area.locator('.workspace-detail').getByRole('button', { name: 'Abrir', exact: true }).click();
  const ticket = area.locator('.workspace-detail').filter({ has: page.getByRole('heading', { name: /^SD-/ }) });
  await expect(ticket.getByText('○ Aberto · Urgente — encaminhamento imediato', { exact: true })).toBeVisible();
  const code = await ticket.getByRole('heading', { name: /^SD-/ }).textContent();
  await ticket.getByLabel('Mensagem', { exact: true }).fill('Qual mensagem apareceu? Relato fictício.');
  await ticket.getByRole('button', { name: 'Solicitar esclarecimento', exact: true }).click();
  await expect(ticket.getByText('? Aguardando esclarecimento · Urgente — encaminhamento imediato', { exact: true })).toBeVisible();
  await ticket.getByLabel('Mensagem', { exact: true }).fill('Resposta fictícia: apareceu aviso descrito pelo solicitante.');
  await ticket.getByRole('button', { name: 'Responder esclarecimento', exact: true }).click();
  await expect(ticket.getByText('↗ Em andamento · Urgente — encaminhamento imediato', { exact: true })).toBeVisible();
  await expect(ticket.getByText(/Qual mensagem apareceu\?/)).toBeVisible();
  await expect(ticket.getByText(/Resposta fictícia:/)).toBeVisible();
  for (const state of ['resolvido', 'reaberto']) {
    await ticket.getByLabel('O que foi feito / justificativa', { exact: true }).fill('Ação fictícia executada e retorno solicitado.');
    await ticket.getByLabel('Estado', { exact: true }).selectOption(state);
    const saved = page.waitForResponse(r => r.url().endsWith(`/api/v1/tickets/${record.ticket_id}`) && r.request().method() === 'PATCH');
    await ticket.getByRole('button', { name: 'Salvar alteração', exact: true }).click();
    expect((await saved).ok()).toBeTruthy();
    await expect(ticket.getByLabel('Estado').locator(`option[value="${state}"]`)).toHaveCount(0);
  }
  await expect(ticket.getByRole('heading', { name: code!, exact: true })).toBeVisible();
  await expect(ticket.getByText(/Reaberturas: 1/)).toBeVisible();
  const data = await (await page.request.get(`/api/v1/tickets/${record.ticket_id}`)).json();
  expect(data.comments).toHaveLength(2);
  expect(data.intervals[0].saida_em).toBeTruthy();
  expect(data.resolved_by).toBeTruthy();
  expect(data.closed_by).toBeTruthy();
  expect(data.reopen_count).toBe(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
});

test('revisão em lote e notificações reais com marcação de leitura', async ({ page }) => {
  const { area, client } = await start(page);
  for (let index = 0; index < 2; index++) {
    await mutation(page, '/records', { client_id: client.id, type: 'finalizacao', texto_original: `Finalização fictícia do lote ${index}.` });
  }
  await area.getByRole('button', { name: 'Minhas revisões', exact: true }).click();
  const cards = area.locator('.work-card').filter({ has: page.getByRole('heading', { name: new RegExp(client.name) }) });
  await expect(cards).toHaveCount(2);
  for (const item of await cards.all()) await item.getByRole('checkbox').check();
  await area.getByRole('button', { name: 'Confirmar selecionados', exact: true }).click();
  await expect(cards).toHaveCount(0);
  await area.getByRole('button', { name: /^Notificações \(/ }).click();
  const unread = area.locator('article').filter({ has: page.getByRole('button', { name: 'Marcar como lida', exact: true }) });
  const before = await unread.count();
  expect(before).toBeGreaterThan(0);
  await unread.first().getByRole('button', { name: 'Marcar como lida', exact: true }).click();
  await expect(unread).toHaveCount(before - 1);
  expect(await page.evaluate(() => localStorage.length)).toBe(0);
});
