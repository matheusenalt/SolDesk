import { test as base, type BrowserContext } from '@playwright/test';
export { expect, type Page, type BrowserContext } from '@playwright/test';

export const test = base.extend<{}, { administratorCookies: Awaited<ReturnType<BrowserContext['cookies']>> }>({
  context: async ({ context, administratorCookies }, use) => {
    await context.addCookies(administratorCookies);
    await use(context);
  },
  administratorCookies: [async ({ browser }, use) => {
    if (!process.env.E2E_ADMIN_EMAIL || !process.env.E2E_ADMIN_PASSWORD) throw new Error('Informe credenciais fictícias pelo ambiente.');
    const context = await browser.newContext();
    try {
      const page = await context.newPage(); await page.goto('/');
      const area = page.getByRole('region', { name: 'Área da organização' });
      await area.getByLabel('E-mail', { exact: true }).fill(process.env.E2E_ADMIN_EMAIL);
      await area.getByLabel('Senha', { exact: true }).fill(process.env.E2E_ADMIN_PASSWORD);
      await area.locator('form').getByRole('button', { name: 'Entrar', exact: true }).click();
      await base.expect(area.getByRole('button', { name: 'Sair', exact: true })).toBeVisible();
      await use(await context.cookies());
    } finally { await context.close(); }
  }, { scope: 'worker' }],
});
