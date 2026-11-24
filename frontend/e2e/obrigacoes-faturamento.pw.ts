import { expect, test, type Page } from '@playwright/test';

const company = {
  id: 'empresa-teste', cnpj: '11222333000181', cnae: '6201501', size: 'MEI',
  regime: 'MEI', municipality: 'Brasília', state: 'DF', provenance: {}, created_at: '2026-01-01',
};
const list = (items: unknown[]) => ({ items, next_cursor: null });
const indicator = { evidence_state: 'absent', verification: 'not_verified', latest_evidence: null };

async function open(page: Page, hash: string) {
  await page.clock.setFixedTime(new Date(2026, 10, 24, 10));
  await page.route('**/api/**', (r) => r.fulfill({ status: 404, json: { detail: 'sem mock' } }));
  await page.route('**/api/auth/session', (r) => r.fulfill({ json: { id: 'conta', email: 'teste@example.invalid' } }));
  await page.route('**/api/auth/csrf', (r) => r.fulfill({ json: { csrf_token: 'csrf' } }));
  await page.route('**/api/empresas?*', (r) => r.fulfill({ json: list([company]) }));
  await page.route('**/api/empresas/empresa-teste/*?*', (r) => r.fulfill({ json: list([]) }));
  await page.route('**/api/empresas/empresa-teste/situacao-fiscal', (r) => r.fulfill({
    json: { registration: indicator, federal_certificate: indicator, obligations: indicator },
  }));
  await page.goto('/' + hash);
}

test('termômetro não inventa valor e salva o faturamento no servidor', async ({ page }) => {
  let amount: string | null = null;
  await open(page, '#inicio');
  await page.route('**/api/empresas/empresa-teste/faturamento/2026', (r) => {
    if (r.request().method() === 'PUT') amount = r.request().postDataJSON().amount;
    return r.fulfill({ json: { year: 2026, amount, updated_at: null } });
  });
  await page.goto('/#dashboard');
  const panel = page.getByLabel('Termômetro de Faturamento');
  await expect(panel.getByText('Informe a receita acumulada em 2026', { exact: false })).toBeVisible();
  await panel.getByRole('button', { name: 'Ajustar receita informada' }).click();
  await panel.getByLabel('Receita Bruta Acumulada em 2026 (R$)').fill('40500');
  await panel.getByRole('button', { name: 'Salvar valor' }).click();
  await expect(panel.getByText('50% do teto', { exact: false })).toBeVisible();
  expect(amount).toBe('40500.00');
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await expect(panel.getByText('50% do teto', { exact: false })).toBeVisible();
  await page.screenshot({ path: 'test-results/termometro.png', fullPage: true });
});

test('gerar obrigações cria só o que falta e ainda não venceu', async ({ page }) => {
  const created: { title: string; due_date: string }[] = [];
  await open(page, '#inicio');
  await page.route('**/api/empresas/empresa-teste/tarefas**', (r) => {
    if (r.request().method() === 'POST') {
      created.push(r.request().postDataJSON());
      return r.fulfill({ status: 201, json: {} });
    }
    return r.fulfill({ json: list(created.map((t, i) => ({ ...t, id: 't' + i, completed: false }))) });
  });
  await page.goto('/#tarefas');
  await page.getByRole('button', { name: 'Gerar obrigações do ano' }).click();
  await page.screenshot({ path: 'test-results/gerar-obrigacoes.png' });
  await page.getByRole('button', { name: 'Confirmar e Gerar 4 Obrigações' }).click();
  await expect.poll(() => created.map((t) => t.due_date)).toEqual([
    '2026-12-20', '2027-01-20', '2027-05-31', '2026-12-31',
  ]);
  await page.getByRole('button', { name: 'Gerar obrigações do ano' }).click();
  await expect(page.getByText('Todas as obrigações do período já estão', { exact: false })).toBeVisible();
});

test('simulador público usa o DAS do MEI de 2026', async ({ page }) => {
  await page.route('**/api/auth/session', (r) => r.fulfill({ status: 401, json: { detail: 'Sessão expirada' } }));
  await page.goto('/');
  const simulator = page.locator('#simulador');
  await expect(simulator.getByText('R$ 86,05', { exact: false })).toBeVisible();
  await simulator.screenshot({ path: 'test-results/simulador.png' });
});
