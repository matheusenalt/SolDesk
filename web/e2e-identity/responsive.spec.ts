import { test, expect, type Page } from './authenticated';

async function mutate(page: Page, path: string, data: unknown) {
  const csrf = await (await page.request.get('/api/v1/auth/csrf')).json();
  const response = await page.request.post('/api/v1' + path, {
    data, headers: { 'X-CSRF-Token': csrf.csrf_token, 'Idempotency-Key': crypto.randomUUID() },
  });
  expect(response.ok()).toBeTruthy();
  return response.json();
}

async function layout(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
  const small = await page.locator('button, input, select, textarea, summary, a').evaluateAll((nodes) => nodes.flatMap((node) => {
    if (!(node instanceof HTMLElement)) return [];
    const box = node.getBoundingClientRect();
    if (!box.width || !box.height) return [];
    const target = node.matches('input[type="checkbox"],input[type="radio"]') ? node.closest('label') || node : node;
    const rect = target.getBoundingClientRect();
    return rect.width < 43.9 || rect.height < 43.9 ? [{ name: node.getAttribute('aria-label') || node.getAttribute('name') || node.textContent?.trim().slice(0, 70), width: rect.width, height: rect.height }] : [];
  }));
  expect(small, 'Alvos de toque visíveis devem medir pelo menos 44 × 44 px').toEqual([]);
  const selected = await page.locator('.workspace-tabs button[aria-current="page"]').evaluateAll(nodes => nodes.filter(node => node.getBoundingClientRect().height > 0).map(node => ({ shadow: getComputedStyle(node).boxShadow, text: getComputedStyle(node).color })));
  expect(selected.every(value => value.shadow.includes(value.text)), 'Seleção usa sublinhado de alto contraste além do acento decorativo').toBeTruthy();
  if ((page.viewportSize()?.width || 0) <= 760) {
    const columns = await page.locator('.workspace-form').evaluateAll(nodes => nodes.filter(node => node.getBoundingClientRect().height > 0).map(node => getComputedStyle(node).gridTemplateColumns.split(' ').length));
    expect(columns.every(count => count === 1), 'Formulários móveis em uma coluna').toBeTruthy();
  }
}

async function keyboardFocus(page: Page) {
  const primary = page.getByRole('group', { name: 'Ações principais' }).getByRole('button', { name: 'Abrir atendimento', exact: true });
  for (let step = 0; step < 100; step += 1) {
    await page.keyboard.press('Tab');
    if (await primary.evaluate(node => document.activeElement === node)) break;
  }
  await expect(primary).toBeFocused();
  expect(await primary.evaluate(node => node.matches(':focus-visible'))).toBeTruthy();
  const metrics = await primary.evaluate(node => {
    const style = getComputedStyle(node);
    const panel = getComputedStyle(node.closest('.workspace')!);
    const luminance = (color: string) => {
      const channels = color.match(/[\d.]+/g)!.slice(0, 3).map(Number).map(value => value / 255).map(value => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
      return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
    };
    const ratio = (a: string, b: string) => {
      const values = [luminance(a), luminance(b)].sort((x, y) => x - y);
      return (values[1] + 0.05) / (values[0] + 0.05);
    };
    return { width: parseFloat(style.outlineWidth), offset: parseFloat(style.outlineOffset), style: style.outlineStyle, contrast: ratio(style.outlineColor, panel.backgroundColor), textContrast: ratio(style.color, style.backgroundColor), theme: document.documentElement.dataset.theme };
  });
  expect(metrics.width).toBeGreaterThanOrEqual(3);
  expect(metrics.offset).toBeGreaterThanOrEqual(2);
  expect(metrics.style).toBe('solid');
  expect(metrics.contrast).toBeGreaterThanOrEqual(3);
  expect(metrics.textContrast).toBeGreaterThanOrEqual(4.5);
  test.info().annotations.push({ type: 'focus', description: JSON.stringify(metrics) });
}

test('gestão e fluxos existentes preservam layout, alvos de toque e foco nos dois temas', async ({ page }, info) => {
  if (info.project.name === 'mobile-web') await page.setViewportSize({ width: 360, height: 800 });
  const client = await mutate(page, '/clients', { name: `Cliente fictício com nome extenso para conferência responsiva ${crypto.randomUUID()}` });
  await page.goto('/');
  const workspace = page.getByRole('region', { name: 'Área da organização', exact: true });
  const navigation = workspace.getByRole('navigation', { name: 'Área da organização', exact: true });
  const actions = workspace.getByRole('group', { name: 'Ações principais' });
  await expect(actions).toBeVisible();
  await layout(page);
  await keyboardFocus(page);
  await actions.getByRole('button', { name: 'Abrir atendimento', exact: true }).click();
  const work = page.getByRole('region', { name: 'Atendimentos', exact: true });
  await expect(work.getByLabel('Relato original', { exact: true })).toBeVisible();
  await work.getByLabel('Cliente', { exact: true }).selectOption(client.id);
  await work.getByLabel('Destino', { exact: true }).selectOption('chamado');
  await layout(page);
  if (info.project.name === 'mobile-web') {
    await page.setViewportSize({ width: 760, height: 900 });
    await layout(page);
    await page.setViewportSize({ width: 360, height: 800 });
  }
  await page.screenshot({ path: info.outputPath('atendimento.png'), fullPage: true });
  await work.getByRole('button', { name: 'Meus registros', exact: true }).click();
  await actions.getByRole('button', { name: 'Abrir atendimento', exact: true }).click();
  await expect(work.getByLabel('Relato original', { exact: true })).toBeVisible();
  await actions.getByRole('button', { name: 'Pesquisar', exact: true }).click();
  const knowledge = page.getByRole('region', { name: 'Base de Conhecimento', exact: true });
  await expect(knowledge.getByRole('button', { name: 'Pesquisar artigos', exact: true })).toBeVisible();
  await expect(knowledge.getByText('Carregando dados…', { exact: true })).toBeHidden();
  await layout(page);
  await navigation.getByRole('button', { name: 'Clientes', exact: true }).click();
  await expect(workspace.getByRole('button', { name: 'Cadastrar cliente', exact: true })).toBeVisible();
  await workspace.getByRole('button', { name: 'Cadastrar cliente', exact: true }).click();
  await layout(page);
  await navigation.getByRole('button', { name: 'Configurações', exact: true }).click();
  await layout(page);
  await navigation.getByRole('button', { name: 'Relatórios', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Relatórios', exact: true })).toBeVisible();
  await layout(page);
  await page.getByRole('button', { name: 'Alternar tema', exact: true }).click();
  await layout(page);
  await navigation.getByRole('button', { name: 'Equipe', exact: true }).click();
  await layout(page);
  await keyboardFocus(page);
});

test('técnico acessa ações reais sem modalidades futuras ou controles administrativos', async ({ page, browser }, info) => {
  const email = `layout-${crypto.randomUUID()}@example.test`;
  const password = `Ficticio!${crypto.randomUUID()}`;
  const invitation = await mutate(page, '/invitations', { email, role: 'tecnico' });
  const context = await browser.newContext({ baseURL: info.project.use.baseURL, viewport: info.project.name === 'mobile-web' ? { width: 360, height: 800 } : { width: 1280, height: 720 } });
  try {
    const csrf = await (await context.request.get('/api/v1/auth/csrf')).json();
    const accepted = await context.request.post('/api/v1/invitations/accept', { data: { email, password, name: 'Técnico fictício de layout', token: invitation.invitation_path.split('=')[1] }, headers: { 'X-CSRF-Token': csrf.csrf_token } });
    expect(accepted.ok()).toBeTruthy();
    const tech = await context.newPage();
    await tech.goto('/');
    const workspace = tech.getByRole('region', { name: 'Área da organização', exact: true });
    const actions = workspace.getByRole('group', { name: 'Ações principais' });
    await expect(actions).toBeVisible();
    await expect(workspace.getByRole('button', { name: 'Equipe', exact: true })).toHaveCount(0);
    await actions.getByRole('button', { name: 'Abrir atendimento', exact: true }).click();
    const destination = tech.getByLabel('Destino', { exact: true });
    await expect(destination.locator('option')).toHaveCount(3);
    expect(await destination.locator('option').evaluateAll(nodes => nodes.map(node => (node as HTMLOptionElement).value))).toEqual(['finalizacao', 'chamado', 'conhecimento']);
    await layout(tech);
    await actions.getByRole('button', { name: 'Pesquisar', exact: true }).click();
    await expect(tech.getByText('Carregando dados…', { exact: true })).toBeHidden();
    await layout(tech);
    await tech.screenshot({ path: info.outputPath('tecnico-pesquisa.png'), fullPage: true });
  } finally { await context.close(); }
});
