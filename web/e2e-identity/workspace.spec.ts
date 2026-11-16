import { test, expect, type Page, type BrowserContext } from '@playwright/test';

let administratorCookies: Awaited<ReturnType<BrowserContext['cookies']>> = [];

async function enter(page: Page, email: string, password: string) {
  await page.goto('/');
  const workspace = page.getByRole('region', { name: 'Área da organização' });
  if ((await page.request.get('/api/v1/me')).ok()) {
    await expect(workspace.getByRole('button', { name: 'Sair', exact: true })).toBeVisible();
    return workspace;
  }
  await workspace.getByLabel('E-mail', { exact: true }).fill(email);
  await workspace.getByLabel('Senha', { exact: true }).fill(password);
  await workspace.locator('form').getByRole('button', { name: 'Entrar', exact: true }).click();
  await expect(workspace.getByRole('button', { name: 'Sair', exact: true })).toBeVisible();
  return workspace;
}

test.beforeAll(async ({ browser }) => {
  if (!process.env.E2E_ADMIN_EMAIL || !process.env.E2E_ADMIN_PASSWORD) {
    throw new Error('Informe credenciais fictícias via E2E_ADMIN_EMAIL/PASSWORD.');
  }
  const session = await browser.newContext();
  try {
    await enter(await session.newPage(), process.env.E2E_ADMIN_EMAIL!, process.env.E2E_ADMIN_PASSWORD!);
    administratorCookies = await session.cookies();
  } finally { await session.close(); }
});

test.beforeEach(async ({ context }) => { await context.addCookies(administratorCookies); });

test('login, cadastro, busca sem acento, edição e consulta reais', async ({ page }) => {
  const workspace = await enter(page, process.env.E2E_ADMIN_EMAIL!, process.env.E2E_ADMIN_PASSWORD!);
  const suffix = `${Date.now()}-${test.info().project.name}`;
  await workspace.getByRole('button', { name: 'Cadastrar cliente', exact: true }).click();
  const form = workspace.locator('form').filter({ has: page.getByRole('heading', { name: 'Cadastrar cliente', exact: true }) });
  await form.getByLabel('Nome', { exact: true }).fill(`Merceária fictícia ${suffix}`);
  await form.getByLabel('Apelido', { exact: true }).fill(`Armazém ${suffix}`);
  await form.getByRole('button', { name: 'Salvar', exact: true }).click();
  await expect(workspace.getByText('✓ Alteração salva', { exact: true })).toBeVisible();
  await workspace.getByLabel('Buscar por nome ou apelido', { exact: true }).fill(`ARMAZEM ${suffix}`);
  await workspace.getByRole('button', { name: 'Buscar por nome ou apelido', exact: true }).click();
  await expect(workspace.getByRole('heading', { name: `Merceária fictícia ${suffix}`, exact: true })).toBeVisible();
  const card = workspace.locator('article').filter({ has: page.getByRole('heading', { name: `Merceária fictícia ${suffix}`, exact: true }) });
  await card.getByRole('button', { name: 'Editar cliente', exact: true }).click();
  const edit = workspace.locator('form').filter({ has: page.getByRole('heading', { name: 'Editar cliente', exact: true }) });
  await edit.getByLabel('Observações').fill('Relato fictício de teste de interface.');
  await edit.getByRole('button', { name: 'Salvar', exact: true }).click();
  await expect(edit).toHaveCount(0);
  await card.getByRole('button', { name: 'Consultar', exact: true }).click();
  await expect(workspace.getByText('Relato fictício de teste de interface.', { exact: true })).toBeVisible();
  await expect(workspace.getByText('Arquivos serão disponibilizados nas próximas fases.')).toBeVisible();
  await workspace.getByRole('button', { name: 'Histórico por cliente', exact: true }).click();
  const work = workspace.getByRole('region', { name: 'Atendimentos', exact: true });
  await expect(work.getByRole('combobox', { name: 'Cliente', exact: true }).locator('option:checked')).toHaveText(`Merceária fictícia ${suffix}`);
  await expect(work.getByText('Finalizações confirmadas: 0', { exact: true })).toBeVisible();
  await workspace.getByRole('button', { name: 'Clientes', exact: true }).click();
  await card.getByRole('button', { name: 'Consultar', exact: true }).click();
  await workspace.getByRole('button', { name: 'Histórico por cliente', exact: true }).click();
  await expect(work.getByRole('combobox', { name: 'Cliente', exact: true }).locator('option:checked')).toHaveText(`Merceária fictícia ${suffix}`);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  expect(await page.evaluate(() => localStorage.length)).toBe(0);
});

test('convite pela equipe e aceite real com token de uso único', async ({ page, browser }) => {
  const workspace = await enter(page, process.env.E2E_ADMIN_EMAIL!, process.env.E2E_ADMIN_PASSWORD!);
  await workspace.getByRole('button', { name: 'Equipe', exact: true }).click();
  const form = workspace.locator('form').filter({ has: page.getByRole('heading', { name: 'Criar convite', exact: true }) });
  const email = `convite-${Date.now()}-${test.info().project.name}@example.test`;
  await form.getByLabel('E-mail').fill(email);
  await form.getByRole('button', { name: 'Criar convite', exact: true }).click();
  const output = workspace.locator('output');
  await expect(output).toBeVisible();
  const url = (await output.textContent())!;
  const second = await browser.newContext();
  try {
    const invited = await second.newPage();
    await invited.goto(url);
    const area = invited.getByRole('region', { name: 'Área da organização' });
    await area.getByLabel('Nome', { exact: true }).fill('Pessoa fictícia convidada');
    await area.getByLabel('E-mail', { exact: true }).fill(email);
    await area.getByLabel('Senha', { exact: true }).fill(crypto.randomUUID());
    await area.locator('form').getByRole('button', { name: 'Entrar', exact: true }).click();
    await expect(area.getByRole('button', { name: 'Cadastrar cliente', exact: true })).toBeVisible();
    expect(await invited.evaluate(() => location.hash)).toBe('');
    await expect(area.getByRole('button', { name: 'Equipe', exact: true })).toHaveCount(0);
  } finally { await second.close(); }
});

test('senha temporária exige troca antes de acessar clientes', async ({ page, browser }) => {
  const workspace = await enter(page, process.env.E2E_ADMIN_EMAIL!, process.env.E2E_ADMIN_PASSWORD!);
  await workspace.getByRole('button', { name: 'Equipe', exact: true }).click();
  const form = workspace.locator('form').filter({ has: page.getByRole('heading', { name: 'Criar com senha temporária', exact: true }) });
  const email = `temporario-${Date.now()}-${test.info().project.name}@example.test`;
  await form.getByLabel('Nome', { exact: true }).fill('Técnico fictício de interface');
  await form.getByLabel('E-mail', { exact: true }).fill(email);
  await form.getByRole('button', { name: 'Criar com senha temporária', exact: true }).click();
  await expect(workspace.locator('output')).toBeVisible();
  const temporary = (await workspace.locator('output').textContent())!;
  const second = await browser.newContext();
  try {
    const technician = await second.newPage();
    const area = await enter(technician, email, temporary);
    await expect(area.getByText('Troque a senha temporária para acessar a organização.')).toBeVisible();
    await expect(area.getByRole('button', { name: 'Cadastrar cliente', exact: true })).toHaveCount(0);
    await area.getByLabel('Senha atual', { exact: true }).fill(temporary);
    await area.getByLabel('Nova senha (12 a 128 caracteres)', { exact: true }).fill(crypto.randomUUID());
    await area.getByRole('button', { name: 'Salvar', exact: true }).click();
    await expect(area.getByRole('button', { name: 'Cadastrar cliente', exact: true })).toBeVisible();
  } finally { await second.close(); }
});
