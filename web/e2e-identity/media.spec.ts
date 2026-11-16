import { test, expect, type Page } from './authenticated';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

function wav() {
  const data = Buffer.alloc(44 + 3200);
  data.write('RIFF', 0); data.writeUInt32LE(data.length - 8, 4); data.write('WAVEfmt ', 8);
  data.writeUInt32LE(16, 16); data.writeUInt16LE(1, 20); data.writeUInt16LE(1, 22);
  data.writeUInt32LE(16000, 24); data.writeUInt32LE(32000, 28); data.writeUInt16LE(2, 32); data.writeUInt16LE(16, 34);
  data.write('data', 36); data.writeUInt32LE(3200, 40); return data;
}
async function mutation(page: Page, path: string, data: unknown) {
  const token = await (await page.request.get('/api/v1/auth/csrf')).json();
  const response = await page.request.post('/api/v1' + path, { data, headers: { 'X-CSRF-Token': token.csrf_token } });
  expect(response.ok()).toBeTruthy(); return response.json();
}
async function start(page: Page, type = 'finalizacao') {
  const client = await mutation(page, '/clients', { name: `Cliente de áudio fictício ${Date.now()} ${test.info().project.name}` });
  await page.goto('/');
  await page.getByRole('region', { name: 'Área da organização' }).getByRole('button', { name: 'Atendimentos', exact: true }).click();
  const area = page.getByRole('region', { name: 'Atendimentos', exact: true });
  await area.getByLabel('Cliente', { exact: true }).selectOption(client.id);
  await area.getByLabel('Destino', { exact: true }).selectOption(type);
  await area.getByLabel('Relato original', { exact: true }).fill('Problema: exemplo fictício no fire bird. Resultado: código 5102 informado; conferir senha, sem valor secreto real.');
  return { area, client };
}
async function sendAudio(page: Page, area: ReturnType<Page['getByRole']>) {
  await area.getByLabel('Escolher áudio', { exact: true }).setInputFiles({ name: 'ficticio.wav', mimeType: 'audio/wav', buffer: wav() });
  const accepted = page.waitForResponse(response => response.url().includes('/audio?revision=') && response.request().method() === 'POST');
  await area.getByRole('button', { name: 'Enviar registro', exact: true }).click();
  const response = await accepted; expect(response.status()).toBe(202); return response.json();
}

test('áudio assíncrono, mock explícito, incerteza e conferência humana antes do histórico', async ({ page }) => {
  const { area, client } = await start(page);
  const value = await sendAudio(page, area);
  const review = area.getByRole('region', { name: 'Processamento do áudio', exact: true });
  await expect(review.getByText(/Texto preparado — exige revisão/)).toBeVisible({ timeout: 30000 });
  await expect(review.getByText(/NÃO reconhece a fala/)).toBeVisible();
  await expect(review.getByText(/Trecho incerto/)).toBeVisible();
  await expect(review.getByText(/Possível credencial/)).toBeVisible();
  const detail = area.locator('.workspace-detail');
  const changed = page.waitForResponse(response => response.url().endsWith(`/records/${value.record.id}`) && response.request().method() === 'PATCH');
  await detail.getByLabel('Texto conferido pelo autor', { exact: true }).fill('Relato fictício conferido manualmente. Código 5102 preservado, sem conclusão acrescentada.');
  await detail.getByRole('button', { name: 'Salvar alteração', exact: true }).click();
  expect((await changed).ok()).toBeTruthy();
  await review.getByLabel('Conferi a transcrição, os trechos incertos e os avisos. O texto foi revisado por mim.', { exact: true }).check();
  await detail.getByRole('button', { name: 'Conferi e confirmo', exact: true }).click();
  await expect(detail.getByText('✓ Confirmado · ✓ Histórico confirmado', { exact: true })).toBeVisible();
  const record = await (await page.request.get(`/api/v1/records/${value.record.id}`)).json();
  expect(record.ocorrido_em).toBe(value.record.ocorrido_em); expect(record.enviado_em).toBe(value.record.enviado_em);
  expect(record.processado_em).toBeTruthy(); expect(record.revisado_em).toBeTruthy();
  expect((await (await page.request.get(`/api/v1/clients/${client.id}/history`)).json()).confirmed_total).toBe(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
});

test('upload no histórico do cliente e download privado com assinatura temporária', async ({ page }) => {
  const { area } = await start(page);
  await area.getByRole('button', { name: 'Histórico por cliente', exact: true }).click();
  const files = area.getByRole('region', { name: 'Arquivos privados', exact: true });
  await files.getByLabel('Arquivo para anexar', { exact: true }).setInputFiles({ name: 'relato-ficticio.txt', mimeType: 'text/plain', buffer: Buffer.from('Documento fictício de teste.') });
  await files.getByRole('button', { name: 'Enviar anexo', exact: true }).click();
  await expect(files.getByText('✓ Arquivo recebido', { exact: true })).toBeVisible();
  await files.getByRole('button', { name: 'Preparar acesso', exact: true }).click();
  const link = files.getByRole('link', { name: /Baixar arquivo/ });
  await expect(link).toBeVisible(); const url = (await link.getAttribute('href'))!;
  expect(url).toContain('/content?expires='); expect(url).toContain('&signature=');
  const download = await page.request.get(url); expect(download.status()).toBe(200); expect(await download.text()).toBe('Documento fictício de teste.');
  expect(await page.evaluate(() => localStorage.length)).toBe(0);
});

test('MediaRecorder real com microfone fictício: prévia, cancelamento e conhecimento continua rascunho', async ({ page, context }) => {
  await context.grantPermissions(['microphone']);
  const { area } = await start(page, 'conhecimento');
  await area.getByRole('button', { name: '● Gravar áudio', exact: true }).click();
  await expect(area.getByText(/● Gravando: 1 segundos/)).toBeVisible();
  await area.getByRole('button', { name: '■ Parar gravação', exact: true }).click();
  await expect(area.getByLabel('Prévia do áudio', { exact: true })).toBeVisible();
  await area.getByRole('button', { name: 'Descartar prévia', exact: true }).click();
  await expect(area.getByLabel('Prévia do áudio', { exact: true })).toHaveCount(0);
  await area.getByRole('button', { name: '● Gravar áudio', exact: true }).click();
  await expect(area.getByText(/● Gravando: 1 segundos/)).toBeVisible();
  await area.getByRole('button', { name: '■ Parar gravação', exact: true }).click();
  await expect(area.getByLabel('Prévia do áudio', { exact: true })).toBeVisible();
  const accepted = page.waitForResponse(response => response.url().includes('/audio?revision=') && response.request().method() === 'POST');
  await area.getByRole('button', { name: 'Enviar registro', exact: true }).click();
  const response = await accepted; expect(response.status()).toBe(202); const value = await response.json();
  const review = area.getByRole('region', { name: 'Processamento do áudio', exact: true });
  await expect(review.getByText(/Texto preparado — exige revisão/)).toBeVisible({ timeout: 30000 });
  await expect(area.getByText('◷ Rascunho de conhecimento; publicação ainda indisponível.', { exact: true })).toBeVisible();
  await expect(area.getByRole('button', { name: 'Conferi e confirmo', exact: true })).toHaveCount(0);
  const record = await (await page.request.get(`/api/v1/records/${value.record.id}`)).json();
  expect(record.publicado_em).toBeNull(); expect(record.article_status).toBe('rascunho');
});

test('worker realmente parado não impede encaminhar e resolver chamado urgente', async ({ page }) => {
  test.skip(process.env.E2E_CONTROL_WORKER !== '1', 'O aceite completo exige E2E_CONTROL_WORKER=1 e Docker local explícito.');
  test.setTimeout(90000);
  const docker = (args: string[]) => execFileSync('docker', ['compose', ...args], { cwd: resolve('..'), stdio: 'pipe' });
  const { area } = await start(page, 'chamado');
  await area.getByLabel('Prioridade', { exact: true }).selectOption('urgente');
  docker(['stop', 'worker']);
  let value: { record: { id: string; ticket_id: string } };
  try {
    value = await sendAudio(page, area);
    const pending = await (await page.request.get(`/api/v1/records/${value.record.id}/processing`)).json();
    expect(pending.jobs[0].status).toBe('aguardando'); expect(pending.jobs[0].priority).toBe('urgente');
    await area.locator('.workspace-detail').getByRole('button', { name: 'Abrir', exact: true }).click();
    const ticket = area.locator('.workspace-detail').filter({ has: page.getByRole('heading', { name: /^SD-/ }) });
    await ticket.getByLabel('Estado', { exact: true }).selectOption('resolvido');
    await ticket.getByRole('button', { name: 'Salvar alteração', exact: true }).click();
    await expect(ticket.getByText('✓ Resolvido · Urgente — encaminhamento imediato', { exact: true })).toBeVisible();
    const files = ticket.getByRole('region', { name: 'Arquivos privados', exact: true });
    await files.getByLabel('Arquivo para anexar', { exact: true }).setInputFiles({ name: 'detalhe.txt', mimeType: 'text/plain', buffer: Buffer.from('Detalhe fictício do chamado.') });
    await files.getByRole('button', { name: 'Enviar anexo', exact: true }).click();
    await expect(files.getByText('✓ Arquivo recebido', { exact: true })).toBeVisible();
  } finally { docker(['up', '-d', '--wait', 'worker']); }
  await expect.poll(async () => (await (await page.request.get(`/api/v1/records/${value.record.id}/processing`)).json()).jobs[0].status, { timeout: 30000 }).toBe('concluido');
  const ticket = await (await page.request.get(`/api/v1/tickets/${value.record.ticket_id}`)).json();
  expect(ticket.status).toBe('resolvido'); expect(ticket.comments.at(-1).kind).toBe('transcricao_mock');
});

test('configuração visual versiona template e cadastra glossário por organização', async ({ page }) => {
  const { area } = await start(page);
  await area.getByRole('button', { name: 'Configurar processamento', exact: true }).click();
  const config = area.getByRole('region', { name: 'Configurar processamento', exact: true });
  const templates = await (await page.request.get('/api/v1/media/templates')).json();
  const latest = templates.find((item: { type: string }) => item.type === 'finalizacao');
  const templateForm = config.locator('form').filter({ has: page.getByText(`Finalização · Versão atual: ${latest.version}`, { exact: true }) });
  await templateForm.locator('input[name="label_0"]').fill('Contexto');
  await templateForm.getByRole('button', { name: 'Salvar configuração', exact: true }).click();
  await expect(config.getByText(`Finalização · Versão atual: ${latest.version + 1}`, { exact: true })).toBeVisible();
  const glossary = config.locator('form').filter({ has: page.getByLabel('Grafia correta', { exact: true }) });
  await glossary.getByLabel('Grafia correta', { exact: true }).fill('TermoFicticio');
  await glossary.getByLabel('Variações de grafia (uma por linha)', { exact: true }).fill('termo ficticio');
  await glossary.getByRole('button', { name: 'Salvar configuração', exact: true }).click();
  await expect(config.getByText('TermoFicticio · termo ficticio', { exact: true })).toBeVisible();
});

test('recusa simulada do microfone mantém envio por digitação', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator.mediaDevices, 'getUserMedia', { value: async () => { throw new DOMException('Permissão recusada para o teste.', 'NotAllowedError'); } });
  });
  const { area } = await start(page);
  await area.getByRole('button', { name: '● Gravar áudio', exact: true }).click();
  await expect(area.getByRole('alert')).toContainText('Não foi possível acessar o microfone. Confira a permissão; você pode enviar um arquivo ou digitar.');
  await area.getByRole('button', { name: 'Enviar registro', exact: true }).click();
  await expect(area.locator('.workspace-detail').getByText('◷ Aguardando revisão · ◷ Provisório — não confirmado', { exact: true })).toBeVisible();
});
