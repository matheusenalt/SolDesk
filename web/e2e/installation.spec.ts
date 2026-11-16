import { test, expect } from '@playwright/test';

test('conexão real, identidade, temas e layout responsivo', async ({ page, request }) => {
  const response = await request.get('/api/v1/server-info');
  expect(response.ok()).toBeTruthy();
  const info = await response.json();
  await page.goto('/');
  await expect(page.getByRole('status')).toHaveText('✓Backend conectado');
  await expect(page.getByText(info.instance_id)).toBeVisible();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Suporte com memória.');
  const originalTheme = await page.locator('html').getAttribute('data-theme');
  await page.getByRole('button', { name: 'Alternar tema' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', originalTheme === 'dark' ? 'light' : 'dark');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({ path: `test-results/${test.info().project.name}-dark.png`, fullPage: true });
});

test('API indisponível mostra erro e permite nova tentativa', async ({ page }) => {
  await page.route('**/api/v1/health', (route) => route.fulfill({ status: 503, body: '{}' }));
  await page.goto('/');
  await expect(page.getByRole('status')).toHaveText('!Servidor indisponível');
  await expect(page.getByRole('alert')).toContainText('Não foi possível consultar o servidor');
  await page.unroute('**/api/v1/health');
  await page.getByRole('button', { name: 'Verificar novamente' }).click();
  await expect(page.getByRole('status')).toHaveText('✓Backend conectado');
});
